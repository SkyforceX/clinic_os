from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from django.db.models import BigIntegerField, Value
from django.db.models.functions import Coalesce

REVENUE_STATUSES = ("APPROVED", "ACTIVE", "FINISHED")
RENEWAL_SOURCE_STATUSES = ("FINISHED",)


def _contract_base():
    from apps.contract.models.contract import Contract

    return Contract.objects.filter(status__in=REVENUE_STATUSES, company__isnull=False)


def _ensure_snapshot(snapshot: dict | None) -> dict:
    return snapshot or build_retention_snapshot()


def _effective_contract_date(start_date, created_at):
    if start_date:
        return start_date
    if created_at:
        return created_at.date()
    return None


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_retention_snapshot() -> dict:
    """
    Snapshot aggregate cho toàn bộ retention analytics.

    Mục tiêu:
    - gom dữ liệu revenue contracts chỉ bằng 1 query lớn
    - cohort / churn / NRR / monthly đều tính lại từ snapshot in-memory
    - tránh N+1 và tránh query lặp cho từng năm / từng tháng / từng company
    """
    from apps.contract.models.contract import Contract

    companies_by_year: dict[int, set[int]] = defaultdict(set)
    revenue_by_year_company: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    month_companies: dict[int, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    month_revenue_by_company: dict[int, dict[int, dict[int, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    first_seen_date_by_company: dict[int, date] = {}
    company_summaries: dict[int, dict[str, Any]] = {}
    finished_companies_by_year: dict[int, set[int]] = defaultdict(set)

    total_duration_days = 0
    duration_count = 0

    revenue_rows = (
        _contract_base()
        .annotate(
            revenue=Coalesce(
                "corporate_profile__grand_total",
                Value(0),
                output_field=BigIntegerField(),
            )
        )
        .values(
            "id",
            "company_id",
            "company__name",
            "contract_number",
            "start_date",
            "end_date",
            "created_at",
            "revenue",
        )
        .order_by("company_id", "start_date", "created_at", "id")
    )

    for row in revenue_rows.iterator(chunk_size=1000):
        company_id = row["company_id"]
        if not company_id:
            continue

        effective_date = _effective_contract_date(row["start_date"], row["created_at"])
        if not effective_date:
            continue

        year = effective_date.year
        month = effective_date.month
        revenue = _safe_int(row["revenue"])

        companies_by_year[year].add(company_id)
        revenue_by_year_company[year][company_id] += revenue
        month_companies[year][month].add(company_id)
        month_revenue_by_company[year][month][company_id] += revenue

        first_seen = first_seen_date_by_company.get(company_id)
        if first_seen is None or effective_date < first_seen:
            first_seen_date_by_company[company_id] = effective_date

        summary = company_summaries.setdefault(
            company_id,
            {
                "company_id": company_id,
                "company_name": row["company__name"] or "–",
                "lifetime_rev": 0,
                "contract_count": 0,
                "first_contract_date": None,
                "last_contract_date": None,
                "last_contract_number": "–",
            },
        )
        summary["lifetime_rev"] += revenue
        summary["contract_count"] += 1

        if summary["first_contract_date"] is None or effective_date < summary["first_contract_date"]:
            summary["first_contract_date"] = effective_date

        if summary["last_contract_date"] is None or effective_date >= summary["last_contract_date"]:
            summary["last_contract_date"] = effective_date
            summary["last_contract_number"] = row["contract_number"] or f"#{row['id']}"

        start_date = row["start_date"]
        end_date = row["end_date"]
        if start_date and end_date and end_date >= start_date:
            total_duration_days += (end_date - start_date).days
            duration_count += 1

    finished_rows = (
        Contract.objects.filter(status__in=RENEWAL_SOURCE_STATUSES, company__isnull=False)
        .values("company_id", "end_date", "updated_at")
        .order_by("company_id")
    )
    for row in finished_rows.iterator(chunk_size=1000):
        year_source = row["end_date"] or (row["updated_at"].date() if row["updated_at"] else None)
        if year_source and row["company_id"]:
            finished_companies_by_year[year_source.year].add(row["company_id"])

    first_year_by_company = {
        company_id: first_date.year
        for company_id, first_date in first_seen_date_by_company.items()
        if first_date
    }
    available_years = sorted(companies_by_year.keys(), reverse=True) or [date.today().year]
    avg_duration_days = round(total_duration_days / duration_count) if duration_count else None

    return {
        "companies_by_year": {year: set(ids) for year, ids in companies_by_year.items()},
        "revenue_by_year_company": {
            year: dict(company_map) for year, company_map in revenue_by_year_company.items()
        },
        "month_companies": {
            year: {month: set(ids) for month, ids in month_map.items()}
            for year, month_map in month_companies.items()
        },
        "month_revenue_by_company": {
            year: {
                month: dict(company_map)
                for month, company_map in month_map.items()
            }
            for year, month_map in month_revenue_by_company.items()
        },
        "first_seen_date_by_company": first_seen_date_by_company,
        "first_year_by_company": first_year_by_company,
        "company_summaries": company_summaries,
        "finished_companies_by_year": {
            year: set(ids) for year, ids in finished_companies_by_year.items()
        },
        "available_years": available_years,
        "avg_duration_days": avg_duration_days,
    }


def _company_ids_for_year(year: int, snapshot: dict | None = None) -> set[int]:
    snapshot = _ensure_snapshot(snapshot)
    return set(snapshot["companies_by_year"].get(year, set()))


def get_retention_kpis(year: int, snapshot: dict | None = None) -> dict:
    snapshot = _ensure_snapshot(snapshot)

    companies_this_year = _company_ids_for_year(year, snapshot)
    companies_prev_year = _company_ids_for_year(year - 1, snapshot)
    retained = companies_this_year & companies_prev_year
    crr = round(len(retained) / len(companies_prev_year) * 100, 1) if companies_prev_year else None

    first_year_by_company = snapshot["first_year_by_company"]
    new_companies = {
        company_id for company_id in companies_this_year
        if first_year_by_company.get(company_id) == year
    }
    churn_companies = companies_prev_year - companies_this_year

    historical_before_prev = {
        company_id
        for company_id, first_year in first_year_by_company.items()
        if first_year <= year - 2
    }
    winback = (companies_this_year & historical_before_prev) - companies_prev_year

    revenue_this_year = snapshot["revenue_by_year_company"].get(year, {})
    revenue_prev_year = snapshot["revenue_by_year_company"].get(year - 1, {})

    rev_returning = sum(revenue_this_year.get(company_id, 0) for company_id in retained)
    rev_new = sum(revenue_this_year.get(company_id, 0) for company_id in new_companies)
    rev_total = sum(revenue_this_year.values())
    rev_base = sum(revenue_prev_year.get(company_id, 0) for company_id in retained)
    nrr = round(rev_returning / rev_base * 100, 1) if rev_base else None

    renewable_companies = set(snapshot["finished_companies_by_year"].get(year - 1, set()))
    renewed = renewable_companies & companies_this_year
    renewal_rate = (
        round(len(renewed) / len(renewable_companies) * 100, 1)
        if renewable_companies else None
    )

    return {
        "year": year,
        "companies_this_year": len(companies_this_year),
        "companies_prev_year": len(companies_prev_year),
        "retained": len(retained),
        "churn_count": len(churn_companies),
        "new_client_count": len(new_companies),
        "winback_count": len(winback),
        "crr": crr,
        "nrr": nrr,
        "renewal_rate": renewal_rate,
        "rev_returning": rev_returning,
        "rev_new": rev_new,
        "rev_total": rev_total,
        "rev_returning_pct": round(rev_returning / rev_total * 100, 1) if rev_total else 0,
        "rev_new_pct": round(rev_new / rev_total * 100, 1) if rev_total else 0,
        "avg_duration_days": snapshot["avg_duration_days"],
        "retained_companies": retained,
        "churn_companies": churn_companies,
        "new_companies": new_companies,
        "winback_companies": winback,
    }


def get_at_risk_contracts(days: int = 90) -> list[dict]:
    from apps.contract.models.contract import Contract

    today = date.today()
    deadline = today + timedelta(days=days)

    qs = (
        Contract.objects.filter(status__in=("APPROVED", "ACTIVE"))
        .filter(end_date__isnull=False, end_date__gte=today, end_date__lte=deadline)
        .select_related("company", "created_by", "corporate_profile")
        .order_by("end_date", "company__name", "id")
    )

    result: list[dict] = []
    for contract in qs:
        days_left = (contract.end_date - today).days
        profile = getattr(contract, "corporate_profile", None)
        created_by = getattr(contract, "created_by", None)
        sale_name = "–"
        if created_by:
            sale_name = created_by.get_full_name() or created_by.username

        result.append(
            {
                "id": contract.id,
                "contract_number": contract.contract_number or f"#{contract.id}",
                "company_name": contract.company.name if contract.company else "–",
                "company_id": contract.company_id,
                "end_date": contract.end_date,
                "days_left": days_left,
                "grand_total": _safe_int(getattr(profile, "grand_total", 0)),
                "sale_name": sale_name,
                "urgency": "critical" if days_left <= 14 else ("warning" if days_left <= 30 else "info"),
            }
        )
    return result


def get_churned_companies(year: int, snapshot: dict | None = None) -> list[dict]:
    snapshot = _ensure_snapshot(snapshot)

    prev_ids = _company_ids_for_year(year - 1, snapshot)
    this_ids = _company_ids_for_year(year, snapshot)
    churn_ids = prev_ids - this_ids

    result: list[dict] = []
    for company_id in churn_ids:
        summary = snapshot["company_summaries"].get(company_id)
        if not summary:
            continue
        result.append(
            {
                "company_id": company_id,
                "company_name": summary["company_name"],
                "last_contract": summary["last_contract_number"],
                "last_date": summary["last_contract_date"],
                "lifetime_rev": summary["lifetime_rev"],
                "total_contracts": summary["contract_count"],
            }
        )

    return sorted(result, key=lambda item: (-item["lifetime_rev"], item["company_name"]))


def get_cohort_retention(base_year: int, num_years: int = 5, snapshot: dict | None = None) -> list[dict]:
    snapshot = _ensure_snapshot(snapshot)

    cohort_companies: dict[int, set[int]] = defaultdict(set)
    for company_id, cohort_year in snapshot["first_year_by_company"].items():
        cohort_companies[cohort_year].add(company_id)

    current_year = date.today().year
    cohort_years = sorted(
        [year for year in cohort_companies if base_year - num_years < year <= base_year],
        reverse=True,
    )

    results: list[dict] = []
    for cohort_year in cohort_years:
        cohort = cohort_companies[cohort_year]
        row = {"cohort_year": cohort_year, "size": len(cohort), "years": []}
        for offset in range(1, num_years + 1):
            target_year = cohort_year + offset
            if target_year > current_year:
                row["years"].append(None)
                continue

            active_in_target = len(cohort & _company_ids_for_year(target_year, snapshot))
            pct = round(active_in_target / len(cohort) * 100, 1) if cohort else 0
            row["years"].append(
                {"year": target_year, "pct": pct, "count": active_in_target}
            )
        results.append(row)

    return results


def get_top_clv_companies(limit: int = 20, snapshot: dict | None = None) -> list[dict]:
    snapshot = _ensure_snapshot(snapshot)

    today = date.today()
    companies = sorted(
        snapshot["company_summaries"].values(),
        key=lambda item: (-item["lifetime_rev"], item["company_name"]),
    )[:limit]

    result: list[dict] = []
    for row in companies:
        first_contract = row["first_contract_date"]
        tenure_years = None
        if first_contract:
            tenure_years = round((today - first_contract).days / 365, 1)

        result.append(
            {
                "company_id": row["company_id"],
                "company_name": row["company_name"],
                "clv": row["lifetime_rev"],
                "contract_count": row["contract_count"],
                "first_contract": first_contract,
                "last_contract": row["last_contract_date"],
                "tenure_years": tenure_years,
                "avg_per_contract": int(row["lifetime_rev"] / row["contract_count"]) if row["contract_count"] else 0,
            }
        )
    return result


def get_monthly_new_vs_returning(year: int, snapshot: dict | None = None) -> dict:
    snapshot = _ensure_snapshot(snapshot)

    monthly_new = [0] * 12
    monthly_returning = [0] * 12
    monthly_rev_new = [0] * 12
    monthly_rev_ret = [0] * 12

    year_month_companies = snapshot["month_companies"].get(year, {})
    year_month_revenue = snapshot["month_revenue_by_company"].get(year, {})

    for month in range(1, 13):
        for company_id in year_month_companies.get(month, set()):
            revenue = year_month_revenue.get(month, {}).get(company_id, 0)
            first_seen = snapshot["first_seen_date_by_company"].get(company_id)
            is_new_in_month = bool(first_seen and first_seen.year == year and first_seen.month == month)

            if is_new_in_month:
                monthly_new[month - 1] += 1
                monthly_rev_new[month - 1] += revenue
            else:
                monthly_returning[month - 1] += 1
                monthly_rev_ret[month - 1] += revenue

    return {
        "monthly_new": monthly_new,
        "monthly_returning": monthly_returning,
        "monthly_rev_new": monthly_rev_new,
        "monthly_rev_ret": monthly_rev_ret,
    }


def get_available_years(snapshot: dict | None = None) -> list[int]:
    snapshot = _ensure_snapshot(snapshot)
    return list(snapshot["available_years"])