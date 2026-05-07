"""
apps/reception/views_stats.py
===============================
Trang thống kê lượt khám doanh nghiệp.
Đặt trong sidebar "Lịch khám Doanh nghiệp".
"""

import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from apps.reception.selectors.stats_selectors import (
    get_active_company_progress,
    get_admin_insights,
    get_chart_data,
    get_company_completion_table,
    get_daily_summary,
    get_patient_checkin_list,
    get_peak_hours,
    get_period_aggregate,
)

LOGIN_URL = "authentication:staff_login"

PERIOD_DAYS = {
    "today":  0,
    "week":   6,
    "month":  29,
    "custom": None,
}


def parse_date_range(request):
    """Đọc period param và trả về (date_from, date_to, period_key)."""
    today  = date.today()
    period = request.GET.get("period", "week")

    if period == "today":
        return today, today, "today"

    if period == "month":
        return today.replace(day=1), today, "month"

    if period == "custom":
        try:
            df = date.fromisoformat(request.GET.get("date_from", ""))
            dt = date.fromisoformat(request.GET.get("date_to", ""))
            if df > dt:
                df, dt = dt, df
            # Giới hạn tối đa 365 ngày
            if (dt - df).days > 364:
                dt = df + timedelta(days=364)
            return df, dt, "custom"
        except (ValueError, TypeError):
            pass

    # Default: 7 ngày gần nhất
    return today - timedelta(days=6), today, "week"


@login_required(login_url=LOGIN_URL)
def checkin_stats(request):
    """Trang thống kê lượt khám — main view."""
    today = date.today()
    date_from, date_to, period = parse_date_range(request)

    # 1. Công ty đang có lịch (chưa kết thúc)
    active_companies = get_active_company_progress(today, actor=request.user)

    # 2. Thống kê theo ngày trong kỳ được chọn
    daily = get_daily_summary(date_from, date_to, actor=request.user)

    # 3. Tổng hợp hôm nay / tuần / tháng (luôn tính cố định)
    period_agg = get_period_aggregate(actor=request.user)

    # 4. Chart data
    chart_data = get_chart_data(daily["rows"])

    # 5. Peak hours
    peak_hours = get_peak_hours(date_from, date_to, actor=request.user)

    # 6. Bảng theo công ty
    company_table = get_company_completion_table(date_from, date_to, actor=request.user)

    # 7. Admin insights
    show_insights = bool(getattr(request.user, "is_superuser", False))
    insights = get_admin_insights(date_from, date_to, actor=request.user) if show_insights else {}

    # Format date_from/to để truyền vào template cho custom picker
    date_from_str = date_from.strftime("%Y-%m-%d")
    date_to_str   = date_to.strftime("%Y-%m-%d")

    return render(request, "reception/checkin_stats.html", {
        "today":              today,
        "date_from":          date_from,
        "date_to":            date_to,
        "date_from_str":      date_from_str,
        "date_to_str":        date_to_str,
        "period":             period,
        "active_companies":   active_companies,
        "daily_rows":         daily["rows"],
        "daily_totals":       daily["totals"],
        "period_agg":         period_agg,
        "chart_data_json":    json.dumps(chart_data, ensure_ascii=False),
        "peak_hours_json":    json.dumps(peak_hours, ensure_ascii=False),
        "company_table":      company_table,
        "insights":           insights,
        "show_insights":      show_insights,
    })


@login_required(login_url=LOGIN_URL)
def checkin_stats_api(request):
    """
    AJAX endpoint để refresh stats panel mà không reload trang.
    GET params: period, date_from, date_to
    """
    today = date.today()
    date_from, date_to, period = parse_date_range(request)

    daily      = get_daily_summary(date_from, date_to, actor=request.user)
    period_agg = get_period_aggregate(actor=request.user)
    chart_data = get_chart_data(daily["rows"])
    peak_hours = get_peak_hours(date_from, date_to, actor=request.user)
    show_insights = bool(getattr(request.user, "is_superuser", False))
    insights   = get_admin_insights(date_from, date_to, actor=request.user) if show_insights else {}

    return JsonResponse({
        "ok":         True,
        "chart_data": chart_data,
        "peak_hours": peak_hours,
        "totals":     daily["totals"],
        "period_agg": period_agg,
        "insights":   insights,
        "show_insights": show_insights,
    })


@login_required(login_url=LOGIN_URL)
def patient_list_api(request):
    """
    AJAX: trả về danh sách bệnh nhân của 1 công ty trong kỳ lọc.

    GET params:
        company_name  — tên công ty (snapshot_company_name)
        date_from     — YYYY-MM-DD
        date_to       — YYYY-MM-DD

    Response JSON:
    {
        ok: true,
        company: str,
        counts: {total, arrived, checked_in, checked_out, deferred, not_arrived},
        patients: [{ma_bn, ho_ten, ngay_sinh, gioi_tinh, status, status_display, status_class, exam_date}, ...]
    }
    """
    company_name = request.GET.get("company_name", "").strip()
    if not company_name:
        return JsonResponse({"ok": False, "error": "Thiếu tên công ty."}, status=400)

    try:
        date_from = date.fromisoformat(request.GET.get("date_from", ""))
        date_to   = date.fromisoformat(request.GET.get("date_to", ""))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Ngày không hợp lệ."}, status=400)

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    patients = get_patient_checkin_list(company_name, date_from, date_to, actor=request.user)

    counts = {
        "total":       len(patients),
        "arrived":     sum(1 for p in patients if p["status"] != "NOT_ARRIVED"),
        "checked_in":  sum(1 for p in patients if p["status"] == "CHECKED_IN"),
        "checked_out": sum(1 for p in patients if p["status"] == "CHECKED_OUT"),
        "deferred":    sum(1 for p in patients if p["status"] == "DEFERRED"),
        "not_arrived": sum(1 for p in patients if p["status"] == "NOT_ARRIVED"),
    }

    return JsonResponse({
        "ok":       True,
        "company":  company_name,
        "counts":   counts,
        "patients": patients,
    })
