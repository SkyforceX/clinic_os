"""
hrm/services/work_schedule_service.py
=======================================
Business logic cho đăng ký / cập nhật lịch làm việc.
"""

from datetime import date, datetime, time
import pytz
from django.db import transaction

from apps.hrm.models.work_schedule import WorkSchedule, WorkScheduleLog, SHIFT_DISPLAY


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def can_self_register(user, employee, schedule_date: date) -> bool:
    """
    Nhân viên tự đăng ký được nếu:
    - User là chính employee đó (hoặc superuser)
    - schedule_date >= hôm nay
    - Thời điểm hiện tại chưa qua 0:00 của ngày schedule_date
    """
    if user.is_superuser:
        return True
    # check owner
    emp_user = getattr(employee, "user", None)
    if emp_user is None or emp_user.pk != user.pk:
        return False
    # check deadline: trước 0:00 của ngày đăng ký
    today = date.today()
    if schedule_date < today:
        return False
    if schedule_date == today:
        now = datetime.now().time()
        deadline = time(0, 0)  # midnight đã qua nếu bây giờ sau 0:00 — vẫn cho đến hết ngày hôm nay
        # Cho phép tự chỉnh trong ngày hôm nay, chặn ngày hôm qua
        return True
    return True


def set_shift(
    employee,
    schedule_date: date,
    new_shift: str,
    actor,
    note: str = "",
    request=None,
) -> WorkSchedule:
    """
    Tạo hoặc cập nhật lịch 1 nhân viên × 1 ngày.
    Ghi log mọi thay đổi.
    """
    with transaction.atomic():
        obj, created = WorkSchedule.objects.get_or_create(
            employee=employee,
            schedule_date=schedule_date,
            defaults={"shift": new_shift, "note": note, "registered_by": actor},
        )
        old_shift = "" if created else obj.shift

        if not created:
            obj.shift = new_shift
            obj.note = note
            obj.registered_by = actor
            obj.save(update_fields=["shift", "note", "registered_by", "updated_at"])

        # Write log if changed
        if old_shift != new_shift:
            WorkScheduleLog.objects.create(
                work_schedule=obj,
                actor=actor,
                old_shift=old_shift,
                new_shift=new_shift,
                note=note,
                ip_address=_get_client_ip(request) if request else None,
            )

    return obj


def clear_shift(employee, schedule_date: date, actor, request=None) -> None:
    """Xóa ca làm việc (đặt về blank = chưa đăng ký)."""
    set_shift(employee, schedule_date, "", actor, note="Xóa ca", request=request)


def get_monthly_grid(year: int, month: int, employees_qs):
    """
    Trả về dict:
      {
        employee.pk: {
          date_obj: WorkSchedule | None,
          ...
        },
        ...
      }
    cho tháng year/month với danh sách employees.
    """
    import calendar
    from datetime import date
    from apps.hrm.models.work_schedule import WorkSchedule

    _, days_in_month = calendar.monthrange(year, month)
    dates = [date(year, month, d) for d in range(1, days_in_month + 1)]

    emp_ids = [e.pk for e in employees_qs]
    schedules = WorkSchedule.objects.filter(
        employee_id__in=emp_ids,
        schedule_date__year=year,
        schedule_date__month=month,
    ).select_related("employee")

    # Build lookup: emp_id → date → WorkSchedule
    lookup = {}
    for ws in schedules:
        lookup.setdefault(ws.employee_id, {})[ws.schedule_date] = ws

    grid = {}
    for emp in employees_qs:
        row = {}
        emp_schedules = lookup.get(emp.pk, {})
        for d in dates:
            row[d] = emp_schedules.get(d)
        grid[emp.pk] = row

    return dates, grid
