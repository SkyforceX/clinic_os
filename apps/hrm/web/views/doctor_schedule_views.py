"""
hrm/web/views/doctor_schedule_views.py
========================================
Quản lý lịch làm việc bác sĩ theo tuần.
HR Admin và Manager có thể tạo / sửa.
Mọi user đã đăng nhập xem được (dùng cho dashboard).
"""

import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.hrm.models.doctor_schedule import DoctorSchedule, DAY_KEYS, SHIFT_LABELS
from apps.hrm.models.employee import Employee, EmployeeStatus
from apps.hrm.policies import HRMPolicy

LOGIN_URL = "authentication:staff_login"

DOCTOR_POSITION_KEYWORDS = ["bác sĩ", "doctor", "bs", "physician"]


def get_week_start(ref_date=None):
    """Trả về thứ Hai của tuần chứa ref_date."""
    ref_date = ref_date or date.today()
    return ref_date - timedelta(days=ref_date.weekday())


def get_doctor_queryset():
    """Lấy danh sách nhân viên là bác sĩ (dựa theo position name)."""
    qs = Employee.objects.filter(
        status__in=[EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION],
    ).select_related("position", "department").order_by("full_name")
    return qs


# ── Danh sách lịch tuần ───────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def doctor_schedule_list(request):
    """Danh sách lịch bác sĩ theo tuần, có thể lọc tuần."""
    try:
        week_offset = int(request.GET.get("week", 0))
    except (ValueError, TypeError):
        week_offset = 0

    today = date.today()
    base_week = get_week_start(today) + timedelta(weeks=week_offset)
    week_end = base_week + timedelta(days=6)

    schedules = (
        DoctorSchedule.objects
        .filter(week_start=base_week)
        .select_related("doctor", "doctor__position", "doctor__department")
        .order_by("doctor__full_name")
    )

    can_manage = (
        HRMPolicy.is_hr_admin(request.user)
        or HRMPolicy.is_manager(request.user)
        or HRMPolicy.is_executive(request.user)
    )

    week_days = [base_week + timedelta(days=i) for i in range(7)]

    return render(request, "hrm/staff/doctor_schedule_list.html", {
        "schedules":    schedules,
        "week_start":   base_week,
        "week_end":     week_end,
        "week_days":    week_days,
        "week_offset":  week_offset,
        "prev_offset":  week_offset - 1,
        "next_offset":  week_offset + 1,
        "today":        today,
        "can_manage":   can_manage,
        "day_keys":     DAY_KEYS,
        "shift_labels": SHIFT_LABELS,
    })


# ── Tạo / sửa lịch tuần cho 1 bác sĩ ─────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def doctor_schedule_edit(request, week_start_str=None, doctor_id=None):
    """
    GET  → Form nhập lịch tuần cho bác sĩ
    POST → Lưu lịch
    """
    if not (
        HRMPolicy.is_hr_admin(request.user)
        or HRMPolicy.is_manager(request.user)
        or HRMPolicy.is_executive(request.user)
    ):
        raise Http404("Bạn không có quyền quản lý lịch bác sĩ.")

    try:
        week_start = date.fromisoformat(week_start_str) if week_start_str else get_week_start()
        week_start = week_start - timedelta(days=week_start.weekday())
    except (ValueError, TypeError):
        week_start = get_week_start()

    week_end = week_start + timedelta(days=6)
    doctors = get_doctor_queryset()

    selected_doctor = None
    if doctor_id:
        selected_doctor = get_object_or_404(Employee, pk=doctor_id)

    existing = {}
    if selected_doctor:
        sched = DoctorSchedule.objects.filter(doctor=selected_doctor, week_start=week_start).first()
        existing = sched.schedule_json if sched else {}

    if request.method == "POST":
        doc_id = request.POST.get("doctor_id") or doctor_id
        if not doc_id:
            messages.error(request, "Vui lòng chọn bác sĩ.")
            return redirect("hrm:doctor_schedule_list")

        doctor = get_object_or_404(Employee, pk=doc_id)
        schedule_data = {}
        for day in DAY_KEYS:
            shift = request.POST.get(f"shift_{day}") or None
            if shift not in ("morning", "afternoon", "all_day", None):
                shift = None
            schedule_data[day] = shift

        note = (request.POST.get("note") or "").strip()[:300]
        week_str = request.POST.get("week_start") or week_start.isoformat()
        try:
            save_week = date.fromisoformat(week_str)
            save_week = save_week - timedelta(days=save_week.weekday())
        except (ValueError, TypeError):
            save_week = week_start

        obj, created = DoctorSchedule.objects.update_or_create(
            doctor=doctor,
            week_start=save_week,
            defaults={
                "schedule_json": schedule_data,
                "note":          note,
                "created_by":    request.user,
            },
        )
        verb = "Đã tạo" if created else "Đã cập nhật"
        messages.success(request, f"{verb} lịch cho {doctor.full_name} tuần {save_week.strftime('%d/%m/%Y')}.")
        return redirect(f"{request.path}?saved=1")

    week_days = [week_start + timedelta(days=i) for i in range(7)]

    return render(request, "hrm/staff/doctor_schedule_edit.html", {
        "doctors":          doctors,
        "selected_doctor":  selected_doctor,
        "week_start":       week_start,
        "week_end":         week_end,
        "week_days":        week_days,
        "existing":         existing,
        "existing_json":    json.dumps(existing, ensure_ascii=False),
        "day_keys":         DAY_KEYS,
        "shift_labels":     SHIFT_LABELS,
    })


# ── Bulk save (API JSON) ───────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require_POST
def doctor_schedule_bulk_save(request):
    """
    POST JSON body:
    {
      "week_start": "2025-06-16",
      "schedules": [
        {"doctor_id": 1, "schedule_json": {"mon": "morning", ...}, "note": "..."},
        ...
      ]
    }
    """
    if not (HRMPolicy.is_hr_admin(request.user) or HRMPolicy.is_manager(request.user)):
        return JsonResponse({"ok": False, "message": "Không có quyền."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "message": "Dữ liệu không hợp lệ."}, status=400)

    week_str = body.get("week_start") or ""
    try:
        week_start = date.fromisoformat(week_str)
        week_start = week_start - timedelta(days=week_start.weekday())
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "message": "Ngày không hợp lệ."}, status=400)

    schedules_data = body.get("schedules") or []
    saved_count = 0
    for item in schedules_data:
        doc_id = item.get("doctor_id")
        if not doc_id:
            continue
        sched_json = item.get("schedule_json") or {}
        note = (item.get("note") or "")[:300]
        clean = {day: sched_json.get(day) for day in DAY_KEYS}
        DoctorSchedule.objects.update_or_create(
            doctor_id=doc_id,
            week_start=week_start,
            defaults={"schedule_json": clean, "note": note, "created_by": request.user},
        )
        saved_count += 1

    return JsonResponse({"ok": True, "saved": saved_count})
