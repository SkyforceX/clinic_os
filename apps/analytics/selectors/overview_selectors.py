"""
analytics/selectors/overview_selectors.py
==========================================
Tất cả query thống kê tổng hợp cho màn hình dashboard Executive.

Nguồn dữ liệu:
  - QuotationDraft       → số lượng báo giá
  - Contract             → số lượng hợp đồng, doanh thu
  - CorporateContractProfile.grand_total → giá trị hợp đồng
  - ContractServiceLine  → dịch vụ trong hợp đồng

Trạng thái được tính là "đã duyệt / thực hiện":
  APPROVED, ACTIVE, FINISHED  (không tính DRAFT, SUBMITTED, TERMINATED, CANCELLED)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth


# ── Constants ────────────────────────────────────────────────────────────────

REVENUE_STATUSES = ("APPROVED", "ACTIVE", "FINISHED")
ALL_CONTRACT_STATUSES = ("APPROVED", "ACTIVE", "FINISHED", "TERMINATED", "CANCELLED")

MONTH_LABELS = [
    "T1", "T2", "T3", "T4", "T5", "T6",
    "T7", "T8", "T9", "T10", "T11", "T12",
]


# ── KPI Tổng hợp ─────────────────────────────────────────────────────────────

def get_kpi_summary(year: int) -> dict:
    """
    Trả về KPI tổng hợp cho năm chọn:
      - total_quotations: tổng báo giá tạo trong năm
      - total_contracts:  tổng hợp đồng (đã duyệt) trong năm
      - total_revenue:    tổng doanh thu (grand_total, APPROVED/ACTIVE/FINISHED)
      - avg_contract_value: giá trị trung bình / hợp đồng
      - yoy_revenue:      doanh thu năm trước (để tính tăng trưởng)
    """
    from apps.contract.models.quotation import QuotationDraft
    from apps.contract.models.contract import Contract
    from apps.contract.models.corporate import CorporateContractProfile

    total_quotations = QuotationDraft.objects.filter(
        created_at__year=year,
    ).count()

    contract_qs = Contract.objects.filter(
        status__in=REVENUE_STATUSES,
    )
    # Dùng start_date nếu có, fallback created_at
    revenue_contracts = contract_qs.filter(
        Q(start_date__year=year) | Q(start_date__isnull=True, created_at__year=year)
    )

    total_contracts = revenue_contracts.count()

    revenue_agg = CorporateContractProfile.objects.filter(
        contract__in=revenue_contracts
    ).aggregate(total=Sum("grand_total"))
    total_revenue = int(revenue_agg["total"] or 0)

    avg_value = total_revenue // total_contracts if total_contracts else 0

    # Năm trước để tính YoY
    prev_contracts = contract_qs.filter(
        Q(start_date__year=year - 1) | Q(start_date__isnull=True, created_at__year=year - 1)
    )
    prev_revenue_agg = CorporateContractProfile.objects.filter(
        contract__in=prev_contracts
    ).aggregate(total=Sum("grand_total"))
    prev_revenue = int(prev_revenue_agg["total"] or 0)

    yoy_pct = None
    if prev_revenue > 0:
        yoy_pct = round((total_revenue - prev_revenue) / prev_revenue * 100, 1)

    return {
        "total_quotations":   total_quotations,
        "total_contracts":    total_contracts,
        "total_revenue":      total_revenue,
        "avg_contract_value": avg_value,
        "prev_revenue":       prev_revenue,
        "yoy_pct":            yoy_pct,
    }


# ── Monthly Trend ─────────────────────────────────────────────────────────────

def get_monthly_quotation_counts(year: int) -> list[int]:
    """Số lượng báo giá tạo theo tháng (12 phần tử)."""
    from apps.contract.models.quotation import QuotationDraft

    rows = (
        QuotationDraft.objects
        .filter(created_at__year=year)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(cnt=Count("id"))
        .order_by("month")
    )
    result = [0] * 12
    for row in rows:
        m = row["month"].month - 1
        result[m] = row["cnt"]
    return result


def get_monthly_contract_counts(year: int) -> list[int]:
    """Số lượng hợp đồng (APPROVED/ACTIVE/FINISHED) ký kết theo tháng."""
    from apps.contract.models.contract import Contract

    rows = (
        Contract.objects
        .filter(
            status__in=REVENUE_STATUSES,
        )
        .filter(
            Q(start_date__year=year) | Q(start_date__isnull=True, created_at__year=year)
        )
        .annotate(
            month=TruncMonth(
                "start_date",
            )
        )
        .values("month")
        .annotate(cnt=Count("id"))
        .order_by("month")
    )

    # Fallback: TruncMonth trên start_date trả None nếu null → cũng annotate created_at
    rows2 = (
        Contract.objects
        .filter(
            status__in=REVENUE_STATUSES,
            start_date__isnull=True,
            created_at__year=year,
        )
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(cnt=Count("id"))
        .order_by("month")
    )

    result = defaultdict(int)
    for row in rows:
        if row["month"]:
            result[row["month"].month] += row["cnt"]
    for row in rows2:
        if row["month"]:
            result[row["month"].month] += row["cnt"]

    return [result.get(m, 0) for m in range(1, 13)]


def get_monthly_revenue(year: int) -> list[int]:
    """
    Doanh thu (grand_total) theo tháng, lấy từ CorporateContractProfile.
    Dùng start_date của Contract, fallback created_at.
    """
    from apps.contract.models.contract import Contract
    from apps.contract.models.corporate import CorporateContractProfile

    contract_ids_by_month: dict[int, list[int]] = defaultdict(list)

    for c in Contract.objects.filter(status__in=REVENUE_STATUSES).filter(
        Q(start_date__year=year) | Q(start_date__isnull=True, created_at__year=year)
    ).only("id", "start_date", "created_at"):
        ref_date = c.start_date or (c.created_at.date() if c.created_at else None)
        if ref_date and ref_date.year == year:
            contract_ids_by_month[ref_date.month].append(c.id)

    result = [0] * 12
    for month, ids in contract_ids_by_month.items():
        agg = CorporateContractProfile.objects.filter(
            contract_id__in=ids
        ).aggregate(s=Sum("grand_total"))
        result[month - 1] = int(agg["s"] or 0)
    return result


# ── Revenue by Sale ───────────────────────────────────────────────────────────

def get_revenue_by_sale(year: int) -> list[dict]:
    """
    Doanh thu theo từng user sale trong năm chọn.
    Trả về list[{"name": str, "revenue": int, "contracts": int}] sort desc.
    """
    from apps.contract.models.contract import Contract
    from apps.contract.models.corporate import CorporateContractProfile
    from django.contrib.auth import get_user_model

    User = get_user_model()

    contracts = (
        Contract.objects
        .filter(
            status__in=REVENUE_STATUSES,
        )
        .filter(
            Q(start_date__year=year) | Q(start_date__isnull=True, created_at__year=year)
        )
        .select_related("created_by", "corporate_profile")
        .prefetch_related("corporate_profile")
    )

    sale_map: dict[int, dict] = {}  # user_id → {name, revenue, contracts}

    for c in contracts:
        profile = getattr(c, "corporate_profile", None)
        grand_total = int(profile.grand_total) if profile else 0
        user = c.created_by
        if user is None:
            uid, name = 0, "Không xác định"
        else:
            uid = user.id
            name = user.get_full_name() or user.username

        if uid not in sale_map:
            sale_map[uid] = {"name": name, "revenue": 0, "contracts": 0}
        sale_map[uid]["revenue"]   += grand_total
        sale_map[uid]["contracts"] += 1

    return sorted(sale_map.values(), key=lambda x: x["revenue"], reverse=True)


# ── Conversion Rate ───────────────────────────────────────────────────────────

def get_conversion_funnel(year: int) -> dict:
    """
    Phễu chuyển đổi: báo giá → hợp đồng.
    """
    from apps.contract.models.quotation import QuotationDraft
    from apps.contract.models.contract import Contract

    total_q = QuotationDraft.objects.filter(created_at__year=year).count()
    total_c = Contract.objects.filter(
        status__in=REVENUE_STATUSES,
    ).filter(
        Q(start_date__year=year) | Q(start_date__isnull=True, created_at__year=year)
    ).count()

    rate = round(total_c / total_q * 100, 1) if total_q else 0
    return {"quotations": total_q, "contracts": total_c, "rate": rate}


# ── Available Years ───────────────────────────────────────────────────────────

def get_available_years() -> list[int]:
    """Danh sách năm có dữ liệu (QuotationDraft hoặc Contract)."""
    from apps.contract.models.quotation import QuotationDraft
    from apps.contract.models.contract import Contract

    q_years = set(
        QuotationDraft.objects.filter(created_at__isnull=False)
        .values_list("created_at__year", flat=True)
        .distinct()
    )
    c_years = set(
        Contract.objects.filter(start_date__isnull=False)
        .values_list("start_date__year", flat=True)
        .distinct()
    )
    c_years2 = set(
        Contract.objects.filter(created_at__isnull=False)
        .values_list("created_at__year", flat=True)
        .distinct()
    )

    all_years = sorted((q_years | c_years | c_years2) or {date.today().year}, reverse=True)
    return all_years
