"""
analytics/selectors/service_selectors.py
==========================================
Thống kê số lượng từng danh mục dịch vụ trong các hợp đồng đã phê duyệt.

Logic:
  - Lấy ContractServiceLine từ Contract có status APPROVED/ACTIVE/FINISHED
  - Group by group_name, item_name
  - Count số hợp đồng có dịch vụ đó (contract_count)
  - Tổng người thụ hưởng = male_count + female_single_count + female_family_count
    từ CorporateContractProfile của từng hợp đồng chứa dịch vụ này
"""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q


REVENUE_STATUSES = ("APPROVED", "ACTIVE", "FINISHED")


def get_service_usage_by_period(year: int, month: int | None = None) -> list[dict]:
    """
    Thống kê số lượng từng dịch vụ trong HĐ đã duyệt theo năm/tháng.

    Trả về list[dict]:
      {
        "group_name":      str,
        "item_name":       str,
        "contract_count":  int,   # số HĐ có dịch vụ này
        "pax_total":       int,   # tổng người (male+fs+ff) từ profile HĐ đó
      }
    Sorted by group_name (display_order via group), rồi contract_count desc.
    """
    from apps.contract.models.contract import Contract, ContractServiceLine
    from apps.contract.models.corporate import CorporateContractProfile

    # ── Lọc hợp đồng theo thời gian ──────────────────────────────────────
    date_filter = Q(start_date__year=year) | Q(start_date__isnull=True, created_at__year=year)
    if month:
        date_filter = (
            Q(start_date__year=year, start_date__month=month)
            | Q(start_date__isnull=True, created_at__year=year, created_at__month=month)
        )

    contract_ids = list(
        Contract.objects
        .filter(status__in=REVENUE_STATUSES)
        .filter(date_filter)
        .values_list("id", flat=True)
    )

    if not contract_ids:
        return []

    # ── Profile map: contract_id → total_pax ──────────────────────────────
    profile_map: dict[int, int] = {}
    for p in CorporateContractProfile.objects.filter(
        contract_id__in=contract_ids
    ).values("contract_id", "male_count", "female_single_count", "female_family_count"):
        pax = (p["male_count"] or 0) + (p["female_single_count"] or 0) + (p["female_family_count"] or 0)
        profile_map[p["contract_id"]] = pax

    # ── Aggregate service lines ───────────────────────────────────────────
    rows = (
        ContractServiceLine.objects
        .filter(contract_id__in=contract_ids)
        .values("group_name", "item_name")
        .annotate(
            contract_count=Count("contract_id", distinct=True),
        )
        .order_by("group_name", "-contract_count", "item_name")
    )

    # Tính pax_total: tổng pax của tất cả HĐ có dịch vụ này
    # (cần sub-query per row — thực hiện bằng Python để tránh N+1 nặng)
    service_contract_map: dict[tuple, set] = defaultdict(set)
    for line in ContractServiceLine.objects.filter(
        contract_id__in=contract_ids
    ).values("group_name", "item_name", "contract_id"):
        key = (line["group_name"] or "", line["item_name"] or "")
        service_contract_map[key].add(line["contract_id"])

    result = []
    for row in rows:
        key = (row["group_name"] or "", row["item_name"] or "")
        cids = service_contract_map.get(key, set())
        pax_total = sum(profile_map.get(cid, 0) for cid in cids)
        result.append({
            "group_name":     row["group_name"] or "Khác",
            "item_name":      row["item_name"]  or "",
            "contract_count": row["contract_count"],
            "pax_total":      pax_total,
        })

    return result


def get_service_usage_grouped(year: int, month: int | None = None) -> list[dict]:
    """
    Trả về dữ liệu đã gom nhóm theo group_name:
    [
      {
        "group_name": str,
        "items": [
          {"item_name": str, "contract_count": int, "pax_total": int},
          ...
        ],
        "group_total_contracts": int,  # max contract_count trong group (unique HĐ)
      },
      ...
    ]
    """
    flat = get_service_usage_by_period(year, month)

    groups: dict[str, dict] = {}
    for row in flat:
        g = row["group_name"]
        if g not in groups:
            groups[g] = {"group_name": g, "items": [], "group_max_contracts": 0}
        groups[g]["items"].append({
            "item_name":     row["item_name"],
            "contract_count": row["contract_count"],
            "pax_total":     row["pax_total"],
        })
        groups[g]["group_max_contracts"] = max(
            groups[g]["group_max_contracts"], row["contract_count"]
        )

    return list(groups.values())


def get_available_months_for_year(year: int) -> list[int]:
    """Tháng có dữ liệu hợp đồng trong năm."""
    from apps.contract.models.contract import Contract

    months = set(
        Contract.objects.filter(
            status__in=REVENUE_STATUSES,
            start_date__year=year,
        ).values_list("start_date__month", flat=True).distinct()
    )
    months2 = set(
        Contract.objects.filter(
            status__in=REVENUE_STATUSES,
            start_date__isnull=True,
            created_at__year=year,
        ).values_list("created_at__month", flat=True).distinct()
    )
    return sorted(months | months2)
