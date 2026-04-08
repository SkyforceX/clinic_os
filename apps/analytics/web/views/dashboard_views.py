from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.analytics.policies import AnalyticsPolicy
from apps.analytics.selectors.overview_selectors import (
    MONTH_LABELS,
    get_available_years,
    get_conversion_funnel,
    get_kpi_summary,
    get_monthly_contract_counts,
    get_monthly_quotation_counts,
    get_monthly_revenue,
    get_revenue_by_sale,
)
from apps.analytics.selectors.service_selectors import (
    get_available_months_for_year,
    get_service_usage_grouped,
)


def _check_access(request):
    """Return None nếu được phép, else HttpResponse 403."""
    if not AnalyticsPolicy.can_view(request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden(
            "<h2>403 – Bạn không có quyền truy cập trang này.</h2>"
            "<p>Chức năng này chỉ dành cho nhóm <strong>Executive</strong>.</p>"
        )
    return None


# ── Overview Dashboard ────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def overview(request):
    denied = _check_access(request)
    if denied:
        return denied

    current_year = date.today().year
    try:
        year = int(request.GET.get("year") or current_year)
    except (ValueError, TypeError):
        year = current_year

    available_years = get_available_years() or [current_year]
    if year not in available_years:
        available_years = sorted(set(available_years) | {year}, reverse=True)

    kpi       = get_kpi_summary(year)
    funnel    = get_conversion_funnel(year)
    monthly_q = get_monthly_quotation_counts(year)
    monthly_c = get_monthly_contract_counts(year)
    monthly_r = get_monthly_revenue(year)
    by_sale   = get_revenue_by_sale(year)

    # Cắt top-10 sale để biểu đồ đẹp
    top_sale = by_sale[:12]

    return render(request, "analytics/staff/overview.html", {
        "year":              year,
        "available_years":   available_years,
        "kpi":               kpi,
        "funnel":            funnel,
        "month_labels_json": MONTH_LABELS,
        "monthly_q_json":    monthly_q,
        "monthly_c_json":    monthly_c,
        "monthly_r_json":    monthly_r,
        "by_sale_json":      top_sale,
        "is_executive":      True,
    })


# ── Service Stats ─────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def service_stats(request):
    denied = _check_access(request)
    if denied:
        return denied

    current_year = date.today().year
    try:
        year = int(request.GET.get("year") or current_year)
    except (ValueError, TypeError):
        year = current_year

    try:
        month = int(request.GET.get("month") or 0) or None
    except (ValueError, TypeError):
        month = None

    available_years  = get_available_years() or [current_year]
    available_months = get_available_months_for_year(year)
    grouped_services = get_service_usage_grouped(year, month)

    # Tìm max contract_count để scale thanh ngang
    max_count = max(
        (item["contract_count"] for g in grouped_services for item in g["items"]),
        default=1,
    )

    MONTH_NAMES = {
        1: "Tháng 1", 2: "Tháng 2", 3: "Tháng 3", 4: "Tháng 4",
        5: "Tháng 5", 6: "Tháng 6", 7: "Tháng 7", 8: "Tháng 8",
        9: "Tháng 9", 10: "Tháng 10", 11: "Tháng 11", 12: "Tháng 12",
    }

    return render(request, "analytics/staff/service_stats.html", {
        "year":             year,
        "month":            month,
        "available_years":  available_years,
        "available_months": available_months,
        "month_names":      MONTH_NAMES,
        "grouped_services": grouped_services,
        "max_count":        max_count,
        "is_executive":     True,
    })
