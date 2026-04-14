"""
targets/services/target_service.py
====================================
CRUD operations cho SalesTarget.
"""
from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.targets.models import PeriodType, SalesTarget, TargetNote

User = get_user_model()


def _validate_period(period_type: str, period_number: int) -> None:
    limits = {
        PeriodType.MONTHLY:   (1, 12),
        PeriodType.QUARTERLY: (1, 4),
        PeriodType.YEARLY:    (1, 1),
    }
    lo, hi = limits.get(period_type, (1, 1))
    if not (lo <= period_number <= hi):
        raise ValidationError(
            f"period_number {period_number} không hợp lệ cho {period_type} (phải từ {lo}–{hi})."
        )


@transaction.atomic
def upsert_target(
    *,
    actor,
    user_id: int | None,
    period_type: str,
    year: int,
    period_number: int,
    revenue_target: int = 0,
    contract_count_target: int = 0,
    quotation_count_target: int = 0,
    pax_target: int = 0,
    new_client_target: int = 0,
    renewal_target: int = 0,
    avg_deal_size_target: int = 0,
    notes: str = "",
) -> SalesTarget:
    """Tạo mới hoặc cập nhật target. Idempotent."""
    _validate_period(period_type, period_number)

    obj, _ = SalesTarget.objects.update_or_create(
        user_id=user_id,
        period_type=period_type,
        year=year,
        period_number=period_number,
        defaults={
            "revenue_target":         revenue_target,
            "contract_count_target":  contract_count_target,
            "quotation_count_target": quotation_count_target,
            "pax_target":             pax_target,
            "new_client_target":      new_client_target,
            "renewal_target":         renewal_target,
            "avg_deal_size_target":   avg_deal_size_target,
            "notes":                  notes,
            "created_by":             actor,
        },
    )
    return obj


@transaction.atomic
def delete_target(*, actor, target: SalesTarget) -> None:
    target.delete()


def add_note(*, actor, target: SalesTarget, body: str) -> TargetNote:
    return TargetNote.objects.create(target=target, author=actor, body=body.strip())


def bulk_upsert_monthly_targets(
    *,
    actor,
    user_id: int | None,
    year: int,
    monthly_revenues: list[int],   # 12 phần tử, index 0 = T1
    monthly_contracts: list[int] | None = None,
) -> list[SalesTarget]:
    """Tiện ích set KPI cả năm 1 lần."""
    results = []
    for m, rev in enumerate(monthly_revenues, start=1):
        cnt = (monthly_contracts[m - 1] if monthly_contracts else 0)
        t = upsert_target(
            actor=actor,
            user_id=user_id,
            period_type=PeriodType.MONTHLY,
            year=year,
            period_number=m,
            revenue_target=rev,
            contract_count_target=cnt,
        )
        results.append(t)
    return results
