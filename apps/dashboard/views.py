"""
dashboard/views.py
==================
Trang tổng quan hệ thống — hiển thị sau khi đăng nhập.
Cập nhật: tích hợp WorkSchedule (lịch toàn phòng khám) thay vì DoctorSchedule.
"""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.dashboard.selectors.selectors import (
    get_active_implementation_plans,
    get_corporate_bookings_by_week,
    get_executive_stats,
    get_my_schedule_this_week,
    get_sales_stats,
    get_staff_stats,
    get_week_bounds,
    get_week_days,
    get_work_schedule_today,
    get_work_schedule_week_summary,
)

# Nhóm thấy toàn bộ số liệu
FULL_ACCESS_GROUPS = {"Executives", "Executive", "Managers", "Manager", "IT Staff"}
# Nhóm Sales Team
SALES_GROUPS = {"Sales Team", "Sales"}
LOGIN_URL = "authentication:staff_login"


def _user_has_group(user, group_names):
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=group_names).exists()


def is_full_access(user):
    """Superadmin, IT Staff, Executives, Managers: thấy toàn bộ số liệu."""
    return _user_has_group(user, FULL_ACCESS_GROUPS)


def is_sales(user):
    """Sales Team: thấy số liệu do chính user đó tạo."""
    if user.is_superuser:
        return False
    return user.groups.filter(name__in=SALES_GROUPS).exists()


@login_required(login_url=LOGIN_URL)
def overview(request):
    today = date.today()
    week_start, week_end = get_week_bounds(today)
    week_days = get_week_days(week_start)

    # ── Shared data ───────────────────────────────────────────────────────────
    implementation_plans = get_active_implementation_plans(today)
    corporate_bookings   = get_corporate_bookings_by_week(week_start, week_end)

    # ── Work schedule (mới: toàn phòng khám) ──────────────────────────────────
    work_schedule_today, schedule_date = get_work_schedule_today(today)
    week_schedule_summary = get_work_schedule_week_summary(week_start, week_end)

    # ── Lịch cá nhân tuần này ─────────────────────────────────────────────────
    my_employee, my_week_schedule = get_my_schedule_this_week(request.user, week_start, week_end)

    # ── Personal stats theo role ──────────────────────────────────────────────
    if is_full_access(request.user):
        personal_stats = get_executive_stats(request.user)
        user_role = "executive"
    elif is_sales(request.user):
        personal_stats = get_sales_stats(request.user)
        user_role = "sales"
    else:
        personal_stats = get_staff_stats(request.user)
        user_role = "staff"

    # ── Week days info (tránh gọi .weekday() trong DTL) ───────────────────────
    vn_day_labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
    week_days_info = []
    for idx, wd in enumerate(week_days):
        ws_summary = week_schedule_summary.get(wd, {})
        week_days_info.append({
            "date":        wd,
            "day_label":   vn_day_labels[idx],
            "is_today":    wd == today,
            "working":     ws_summary.get("working", 0),
        })

    # Tổng working hôm nay
    today_summary = week_schedule_summary.get(today, {})

    return render(request, "dashboard/staff/overview.html", {
        "today":                  today,
        "week_start":             week_start,
        "week_end":               week_end,
        "week_days":              week_days,
        "week_days_info":         week_days_info,
        # Kế hoạch & booking
        "implementation_plans":   implementation_plans,
        "corporate_bookings":     corporate_bookings,
        # Lịch làm việc
        "work_schedule_today":    work_schedule_today,
        "schedule_date":          schedule_date,
        "today_working_count":    today_summary.get("working", 0),
        "today_total_count":      sum(v for k, v in today_summary.items() if k != "working"),
        # Lịch cá nhân
        "my_employee":            my_employee,
        "my_week_schedule":       my_week_schedule,
        # Stats
        "personal_stats":         personal_stats,
        "user_role":              user_role,
    })
