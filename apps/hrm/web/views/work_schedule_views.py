"""
hrm/web/views/work_schedule_views.py
======================================
Lịch làm việc toàn phòng khám theo tháng.

Phân quyền:
  - HR Admin / Manager / Superuser: xem + chỉnh sửa bất kỳ
  - Nhân viên thường: xem toàn bộ, chỉ tự sửa lịch của bản thân trước 0:00 ngày đó
"""

import calendar
import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.hrm.models.department import Department
from apps.hrm.models.employee import Employee, EmployeeStatus
from apps.hrm.models.work_schedule import (
    WorkSchedule, WorkScheduleLog,
    SHIFT_CHOICES, SHIFT_DISPLAY,
)
from apps.hrm.policies import HRMPolicy
from apps.hrm.services.work_schedule_service import (
    set_shift, can_self_register, get_monthly_grid,
)

LOGIN_URL = "authentication:staff_login"

VALID_SHIFTS = {"F", "S", "C", "L", "O", ""}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_hr_admin(user):
    return user.is_superuser or HRMPolicy.is_hr_admin(user) or HRMPolicy.is_manager(user)


def _get_my_employee(user):
    try:
        return user.employee_profile
    except Exception:
        return None


def _month_nav(year, month):
    if month == 1:
        return (year - 1, 12), (year, month + 1)
    if month == 12:
        return (year, month - 1), (year + 1, 1)
    return (year, month - 1), (year, month + 1)


# ── Main view ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def work_schedule_month(request):
    """
    Hiển thị lịch làm việc toàn phòng khám theo tháng.
    Group by Department, mỗi nhân viên 1 hàng, cột = ngày trong tháng.
    """
    today = date.today()

    # Parse month/year
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if not (1 <= month <= 12):
            raise ValueError
        if year < 2020 or year > 2100:
            raise ValueError
    except (ValueError, TypeError):
        year, month = today.year, today.month

    _, days_in_month = calendar.monthrange(year, month)
    dates = [date(year, month, d) for d in range(1, days_in_month + 1)]

    # Load all active employees with department
    employees = (
        Employee.objects
        .filter(status__in=[EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION])
        .select_related("department", "position", "user")
        .order_by("department__display_order", "department__name", "full_name")
    )

    # Load schedule grid
    emp_ids = [e.pk for e in employees]
    schedules_qs = WorkSchedule.objects.filter(
        employee_id__in=emp_ids,
        schedule_date__year=year,
        schedule_date__month=month,
    )
    # Build lookup: (emp_id, date) → shift
    lookup = {}
    for ws in schedules_qs:
        lookup[(ws.employee_id, ws.schedule_date)] = ws.shift

    # Group by department
    dept_map = {}
    for emp in employees:
        dept = emp.department
        dept_key = dept.pk if dept else 0
        dept_name = dept.name if dept else "Chưa phân phòng"
        dept_order = dept.display_order if dept else 999
        if dept_key not in dept_map:
            dept_map[dept_key] = {
                "dept_id": dept_key,
                "dept_name": dept_name,
                "dept_order": dept_order,
                "employees": [],
            }
        dept_map[dept_key]["employees"].append(emp)

    departments = sorted(dept_map.values(), key=lambda x: (x["dept_order"], x["dept_name"]))

    is_admin = _is_hr_admin(request.user)
    my_employee = _get_my_employee(request.user)
    my_emp_id = my_employee.pk if my_employee else None

    (prev_year, prev_month), (next_year, next_month) = _month_nav(year, month)

    # Build day of week labels
    day_labels = []
    weekday_names = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    for d in dates:
        day_labels.append({
            "date": d,
            "day": d.day,
            "weekday": weekday_names[d.weekday()],
            "is_today": d == today,
            "is_sunday": d.weekday() == 6,
            "is_saturday": d.weekday() == 5,
        })

    # Stats for display
    shift_stats = {s: 0 for s, _ in SHIFT_CHOICES}
    shift_stats[""] = 0
    for ws in schedules_qs:
        shift_stats[ws.shift] = shift_stats.get(ws.shift, 0) + 1

    return render(request, "hrm/staff/work_schedule_month.html", {
        "year": year,
        "month": month,
        "month_name": f"Tháng {month:02d}/{year}",
        "dates": dates,
        "day_labels": day_labels,
        "departments": departments,
        "lookup_json": json.dumps({
            f"{eid}_{d.isoformat()}": s
            for (eid, d), s in lookup.items()
        }),
        "lookup": lookup,
        "is_admin": is_admin,
        "my_emp_id": my_emp_id,
        "today": today,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "shift_display": SHIFT_DISPLAY,
        "shift_choices": [("", "Xóa / Chưa đăng ký")] + list(SHIFT_CHOICES),
        "shift_stats": shift_stats,
    })


# ── AJAX: set shift ───────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require_POST
def work_schedule_set_shift(request):
    """
    AJAX POST: { employee_id, date: "YYYY-MM-DD", shift: "F"|"S"|"C"|"L"|"O"|"" }
    Returns: { ok, shift, shift_label, shift_css }
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "Dữ liệu không hợp lệ"}, status=400)

    emp_id = body.get("employee_id")
    date_str = body.get("date", "")
    new_shift = body.get("shift", "")

    if new_shift not in VALID_SHIFTS:
        return JsonResponse({"ok": False, "error": "Mã ca không hợp lệ"}, status=400)

    try:
        schedule_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Ngày không hợp lệ"}, status=400)

    try:
        employee = Employee.objects.select_related("user").get(pk=emp_id)
    except Employee.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Nhân viên không tồn tại"}, status=404)

    user = request.user

    # Permission check
    if _is_hr_admin(user):
        pass  # HR Admin full access
    elif can_self_register(user, employee, schedule_date):
        pass  # Self registration
    else:
        return JsonResponse({"ok": False, "error": "Bạn không có quyền chỉnh sửa lịch này"}, status=403)

    # Additional check: employee cannot edit past dates (before today)
    if not _is_hr_admin(user):
        today = date.today()
        if schedule_date < today:
            return JsonResponse({"ok": False, "error": "Không thể sửa lịch ngày đã qua"}, status=403)

    ws = set_shift(
        employee=employee,
        schedule_date=schedule_date,
        new_shift=new_shift,
        actor=user,
        note=body.get("note", ""),
        request=request,
    )

    disp = SHIFT_DISPLAY.get(new_shift, {"label": "", "title": "Chưa đăng ký", "css": "shift-empty"})
    return JsonResponse({
        "ok": True,
        "shift": new_shift,
        "label": disp["label"],
        "title": disp["title"],
        "css": disp["css"],
    })


# ── Log view ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def work_schedule_log(request):
    """Xem lịch sử thay đổi (chỉ HR Admin / superuser)."""
    if not _is_hr_admin(request.user):
        from django.shortcuts import redirect
        from django.contrib import messages
        messages.error(request, "Bạn không có quyền xem lịch sử.")
        return redirect("hrm:work_schedule_month")

    logs = (
        WorkScheduleLog.objects
        .select_related("work_schedule", "work_schedule__employee", "actor")
        .order_by("-created_at")[:300]
    )
    return render(request, "hrm/staff/work_schedule_log.html", {
        "logs": logs,
        "shift_display": SHIFT_DISPLAY,
    })
