"""
dashboard/views.py
==================
Trang tổng quan hệ thống — hiển thị sau khi đăng nhập.
"""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.dashboard.selectors.selectors import (
    get_active_implementation_plans,
    get_corporate_bookings_by_week,
    get_doctor_schedules_for_week,
    get_executive_stats,
    get_staff_stats,
    get_week_bounds,
    get_week_days,
)

EXECUTIVE_GROUPS = {"Executive", "Executives", "Manager", "Managers"}
LOGIN_URL = "authentication:staff_login"


def is_executive_or_manager(user):
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=EXECUTIVE_GROUPS).exists()


@login_required(login_url=LOGIN_URL)
def overview(request):
    today = date.today()
    week_start, week_end = get_week_bounds(today)
    week_days = get_week_days(week_start)

    implementation_plans  = get_active_implementation_plans(today)
    corporate_bookings    = get_corporate_bookings_by_week(week_start, week_end)
    doctor_schedules      = get_doctor_schedules_for_week(week_start)

    from apps.hrm.models.doctor_schedule import DAY_KEYS, DAY_LABELS, SHIFT_LABELS

    if is_executive_or_manager(request.user):
        personal_stats = get_executive_stats(request.user)
        user_role = "executive"
    else:
        personal_stats = get_staff_stats(request.user)
        user_role = "staff"

    # Tạo cấu trúc tuần kèm ngày cho template (tránh gọi .weekday trong DTL)
    week_days_info = []
    day_key_list = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    vn_day_labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
    for idx, wd in enumerate(week_days):
        week_days_info.append({
            "date":      wd,
            "day_key":   day_key_list[idx],
            "day_label": vn_day_labels[idx],
            "is_today":  wd == today,
        })

    return render(request, "dashboard/staff/overview.html", {
        "today":                today,
        "week_start":           week_start,
        "week_end":             week_end,
        "week_days":            week_days,
        "week_days_info":       week_days_info,
        "implementation_plans": implementation_plans,
        "corporate_bookings":   corporate_bookings,
        "doctor_schedules":     doctor_schedules,
        "personal_stats":       personal_stats,
        "user_role":            user_role,
        "day_keys":             DAY_KEYS,
        "day_labels":           DAY_LABELS,
        "shift_labels":         SHIFT_LABELS,
    })
