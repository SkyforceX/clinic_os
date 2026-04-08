"""
targets/selectors/achievement_selectors.py
===========================================
Tính thực tế (actual) và so sánh với target cho từng sale / kỳ.

Thực tế lấy từ:
  - Contract (APPROVED / ACTIVE / FINISHED)  → doanh thu, số HĐ
  - CorporateContractProfile.grand_total      → doanh thu
  - QuotationDraft                            → số báo giá
  - Company                                   → KH mới (first contract year)
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum

from apps.targets.models import PeriodType, SalesTarget

User = get_user_model()

REVENUE_STATUSES = ("APPROVED", "ACTIVE", "FINISHED")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _period_date_range(period_type: str, year: int, period_number: int):
    """Trả về (date_from, date_to) cho kỳ."""
    if period_type == PeriodType.MONTHLY:
        _, last_day = calendar.monthrange(year, period_number)
        return date(year, period_number, 1), date(year, period_number, last_day)
    if period_type == PeriodType.QUARTERLY:
        m_start = (period_number - 1) * 3 + 1
        m_end   = m_start + 2
        _, last_day = calendar.monthrange(year, m_end)
        return date(year, m_start, 1), date(year, m_end, last_day)
    # YEARLY
    return date(year, 1, 1), date(year, 12, 31)


def _contract_qs_for_period(date_from, date_to, user_id=None):
    """QuerySet Contract đã duyệt trong kỳ."""
    from apps.contract.models.contract import Contract

    q_date = (
        Q(start_date__gte=date_from, start_date__lte=date_to)
        | Q(start_date__isnull=True,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to)
    )
    qs = Contract.objects.filter(status__in=REVENUE_STATUSES).filter(q_date)
    if user_id:
        qs = qs.filter(created_by_id=user_id)
    return qs


def _quotation_qs_for_period(date_from, date_to, user_id=None):
    from apps.contract.models.quotation import QuotationDraft
    qs = QuotationDraft.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )
    if user_id:
        qs = qs.filter(created_by_id=user_id)
    return qs


def _revenue_for_contracts(contract_qs) -> int:
    from apps.contract.models.corporate import CorporateContractProfile
    agg = CorporateContractProfile.objects.filter(
        contract__in=contract_qs
    ).aggregate(s=Sum("grand_total"))
    return int(agg["s"] or 0)


def _new_clients_in_period(date_from, date_to, user_id=None) -> int:
    """
    KH mới = Company có HĐ đầu tiên (ever) nằm trong kỳ này.
    """
    from apps.contract.models.contract import Contract

    # company_id → ngày HĐ đầu tiên
    all_firsts = (
        Contract.objects
        .filter(status__in=REVENUE_STATUSES)
        .values("company_id")
        .annotate(first=Min_date("start_date", "created_at"))
    )
    # Dùng raw approach vì ORM không có Min cross-field đơn giản:
    from django.db.models.functions import Coalesce
    from django.db.models import Min as DMin
    from django.db.models import F

    qs = Contract.objects.filter(status__in=REVENUE_STATUSES)
    if user_id:
        qs = qs.filter(created_by_id=user_id)

    # Tìm company_id có start_date/created_at trong kỳ VÀ không có HĐ nào trước kỳ
    companies_in_period = set(
        qs.filter(
            Q(start_date__gte=date_from, start_date__lte=date_to)
            | Q(start_date__isnull=True,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to)
        ).values_list("company_id", flat=True).distinct()
    )

    new_count = 0
    for company_id in companies_in_period:
        has_older = Contract.objects.filter(
            company_id=company_id,
            status__in=REVENUE_STATUSES,
        ).filter(
            Q(start_date__lt=date_from)
            | Q(start_date__isnull=True, created_at__date__lt=date_from)
        ).exists()
        if not has_older:
            new_count += 1
    return new_count


def _pax_for_contracts(contract_qs) -> int:
    from apps.contract.models.corporate import CorporateContractProfile
    agg = CorporateContractProfile.objects.filter(
        contract__in=contract_qs
    ).aggregate(
        s=Sum(
            django_models.ExpressionWrapper(
                django_models.F("male_count")
                + django_models.F("female_single_count")
                + django_models.F("female_family_count"),
                output_field=django_models.IntegerField(),
            )
        )
    )
    return int(agg["s"] or 0)


# monkey-patch để tránh import lỗi
import django.db.models as django_models


# ── Main achievement calculator ────────────────────────────────────────────────

def compute_achievement(target: SalesTarget) -> dict:
    """
    Tính actual vs target cho 1 SalesTarget.

    Returns dict:
      revenue_actual, revenue_target, revenue_pct,
      contract_actual, contract_target, contract_pct,
      quotation_actual, quotation_target, quotation_pct,
      pax_actual, pax_target, pax_pct,
      new_client_actual, new_client_target, new_client_pct,
      gap_revenue, on_track (bool), run_rate_pct,
      status: "exceeded" | "on_track" | "at_risk" | "behind"
    """
    date_from, date_to = _period_date_range(
        target.period_type, target.year, target.period_number
    )
    uid = target.user_id

    contract_qs    = _contract_qs_for_period(date_from, date_to, uid)
    quotation_qs   = _quotation_qs_for_period(date_from, date_to, uid)

    rev_actual      = _revenue_for_contracts(contract_qs)
    contract_actual = contract_qs.count()
    quotation_actual= quotation_qs.count()
    pax_actual      = _pax_for_contracts(contract_qs)
    new_client_actual = _new_clients_in_period(date_from, date_to, uid)

    def pct(actual, tgt):
        if not tgt:
            return None
        return round(actual / tgt * 100, 1)

    rev_pct = pct(rev_actual, target.revenue_target)

    # ── Run-rate: dựa trên ngày đã qua trong kỳ ───────────────────────────
    today = date.today()
    total_days  = (date_to - date_from).days + 1
    elapsed_days = max(min((today - date_from).days + 1, total_days), 1)
    elapsed_pct  = elapsed_days / total_days  # 0.0–1.0

    run_rate_pct = None
    if target.revenue_target and elapsed_pct > 0:
        projected = rev_actual / elapsed_pct
        run_rate_pct = round(projected / target.revenue_target * 100, 1)

    # ── Status ────────────────────────────────────────────────────────────
    if rev_pct is None:
        status = "no_target"
    elif rev_pct >= 100:
        status = "exceeded"
    elif run_rate_pct and run_rate_pct >= 90:
        status = "on_track"
    elif run_rate_pct and run_rate_pct >= 70:
        status = "at_risk"
    else:
        status = "behind"

    return {
        "revenue_actual":   rev_actual,
        "revenue_target":   target.revenue_target,
        "revenue_pct":      rev_pct,
        "contract_actual":  contract_actual,
        "contract_target":  target.contract_count_target,
        "contract_pct":     pct(contract_actual, target.contract_count_target),
        "quotation_actual": quotation_actual,
        "quotation_target": target.quotation_count_target,
        "quotation_pct":    pct(quotation_actual, target.quotation_count_target),
        "pax_actual":       pax_actual,
        "pax_target":       target.pax_target,
        "pax_pct":          pct(pax_actual, target.pax_target),
        "new_client_actual":  new_client_actual,
        "new_client_target":  target.new_client_target,
        "new_client_pct":     pct(new_client_actual, target.new_client_target),
        "gap_revenue":      target.revenue_target - rev_actual,
        "run_rate_pct":     run_rate_pct,
        "elapsed_pct":      round(elapsed_pct * 100, 0),
        "status":           status,
        "date_from":        date_from,
        "date_to":          date_to,
    }


def get_team_dashboard(period_type: str, year: int, period_number: int) -> list[dict]:
    """
    Tổng hợp achievement của tất cả sale có target trong kỳ.
    Sort: exceeded > on_track > at_risk > behind.
    """
    targets = SalesTarget.objects.filter(
        period_type=period_type,
        year=year,
        period_number=period_number,
        user__isnull=False,
    ).select_related("user")

    STATUS_ORDER = {"exceeded": 0, "on_track": 1, "at_risk": 2, "behind": 3, "no_target": 4}

    results = []
    for t in targets:
        ach = compute_achievement(t)
        results.append({
            "target":      t,
            "user_name":   t.user.get_full_name() or t.user.username,
            "achievement": ach,
        })

    results.sort(key=lambda x: STATUS_ORDER.get(x["achievement"]["status"], 9))
    return results


def get_monthly_trend_for_user(user_id, year: int) -> list[dict]:
    """
    12 tháng actual revenue + target cho 1 sale (hoặc team nếu user_id=None).
    """
    import calendar as cal_mod

    rows = []
    for m in range(1, 13):
        _, last = cal_mod.monthrange(year, m)
        df, dt  = date(year, m, 1), date(year, m, last)
        cqs     = _contract_qs_for_period(df, dt, user_id)
        rev     = _revenue_for_contracts(cqs)

        target_obj = SalesTarget.objects.filter(
            user_id=user_id,
            period_type=PeriodType.MONTHLY,
            year=year,
            period_number=m,
        ).first()
        tgt = target_obj.revenue_target if target_obj else 0

        rows.append({
            "month":   m,
            "label":   f"T{m}",
            "actual":  rev,
            "target":  tgt,
            "pct":     round(rev / tgt * 100, 1) if tgt else None,
        })
    return rows


def get_leaderboard(period_type: str, year: int, period_number: int) -> list[dict]:
    """
    Xếp hạng tất cả sale theo revenue actual trong kỳ (không cần có target).
    """
    from apps.contract.models.contract import Contract
    from apps.contract.models.corporate import CorporateContractProfile

    date_from, date_to = _period_date_range(period_type, year, period_number)

    contracts = (
        Contract.objects
        .filter(status__in=REVENUE_STATUSES)
        .filter(
            Q(start_date__gte=date_from, start_date__lte=date_to)
            | Q(start_date__isnull=True,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to)
        )
        .select_related("created_by", "corporate_profile")
    )

    sale_map: dict[int, dict] = {}
    for c in contracts:
        profile = getattr(c, "corporate_profile", None)
        rev  = int(profile.grand_total) if profile else 0
        user = c.created_by
        uid  = user.id if user else 0
        name = (user.get_full_name() or user.username) if user else "Không xác định"
        if uid not in sale_map:
            sale_map[uid] = {"name": name, "revenue": 0, "contracts": 0, "has_target": False}
        sale_map[uid]["revenue"]   += rev
        sale_map[uid]["contracts"] += 1

    # Đánh dấu có target không
    targets = SalesTarget.objects.filter(
        period_type=period_type, year=year, period_number=period_number,
        user__isnull=False,
    ).values_list("user_id", "revenue_target")
    target_map = {uid: tgt for uid, tgt in targets}

    result = []
    for uid, row in sale_map.items():
        tgt = target_map.get(uid, 0)
        row["revenue_target"] = tgt
        row["attainment_pct"] = round(row["revenue"] / tgt * 100, 1) if tgt else None
        row["has_target"]     = tgt > 0
        result.append(row)

    return sorted(result, key=lambda x: x["revenue"], reverse=True)


def get_available_periods(period_type: str) -> list[tuple[int, int]]:
    """Danh sách (year, period_number) có target."""
    qs = (
        SalesTarget.objects
        .filter(period_type=period_type)
        .values_list("year", "period_number")
        .distinct()
        .order_by("-year", "-period_number")
    )
    return list(qs)
