from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.retention.policies import RetentionPolicy
from apps.retention.selectors.retention_selectors import (
    build_retention_snapshot,
    get_at_risk_contracts,
    get_available_years,
    get_churned_companies,
    get_cohort_retention,
    get_monthly_new_vs_returning,
    get_retention_kpis,
    get_top_clv_companies,
)

MONTH_LABELS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12"]
AT_RISK_DAY_OPTIONS = (30, 60, 90, 180)


def _deny(request):
    if not RetentionPolicy.can_view(request.user):
        return HttpResponseForbidden(
            "<h2>403 – Chức năng này dành cho Manager / Executive.</h2>"
        )
    return None


@login_required(login_url="authentication:staff_login")
def retention_overview(request):
    denied = _deny(request)
    if denied:
        return denied

    current_year = date.today().year
    try:
        year = int(request.GET.get("year") or current_year)
    except (TypeError, ValueError):
        year = current_year

    snapshot = build_retention_snapshot()
    available_years = get_available_years(snapshot=snapshot) or [current_year]
    if year not in available_years:
        year = available_years[0]

    kpis = get_retention_kpis(year, snapshot=snapshot)
    monthly = get_monthly_new_vs_returning(year, snapshot=snapshot)
    at_risk = get_at_risk_contracts(days=90)
    churn = get_churned_companies(year, snapshot=snapshot)[:15]
    clv_top = get_top_clv_companies(limit=15, snapshot=snapshot)
    cohort = get_cohort_retention(base_year=year, num_years=4, snapshot=snapshot)

    return render(
        request,
        "retention/staff/overview.html",
        {
            "year": year,
            "available_years": available_years,
            "kpis": kpis,
            "monthly": monthly,
            "at_risk_30": [row for row in at_risk if row["days_left"] <= 30],
            "at_risk_all": at_risk,
            "churn_list": churn,
            "clv_top": clv_top,
            "cohort": cohort,
            "cohort_offsets": [1, 2, 3, 4],
            "month_labels": MONTH_LABELS,
            "monthly_new_json": monthly["monthly_new"],
            "monthly_returning_json": monthly["monthly_returning"],
            "monthly_rev_new_json": monthly["monthly_rev_new"],
            "monthly_rev_ret_json": monthly["monthly_rev_ret"],
        },
    )


@login_required(login_url="authentication:staff_login")
def at_risk_detail(request):
    denied = _deny(request)
    if denied:
        return denied

    try:
        days = int(request.GET.get("days") or 90)
    except (TypeError, ValueError):
        days = 90

    if days not in AT_RISK_DAY_OPTIONS:
        days = 90

    at_risk = get_at_risk_contracts(days=days)
    return render(
        request,
        "retention/staff/at_risk.html",
        {
            "at_risk": at_risk,
            "days": days,
            "days_options": AT_RISK_DAY_OPTIONS,
        },
    )