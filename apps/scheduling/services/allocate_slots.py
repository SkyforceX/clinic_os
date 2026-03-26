from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.scheduling.models import ScheduleSlot, SlotType


MAX_AM_LIMIT = 100
MAX_PM_LIMIT = 100
MIN_PER_SHIFT_WHEN_AVAILABLE = 10


def _working_days(contract):
    if not contract.start_date or not contract.end_date:
        raise ValidationError("Hợp đồng chưa có ngày bắt đầu/kết thúc.")

    if contract.end_date < contract.start_date:
        raise ValidationError("Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.")

    return [
        day
        for day in (
            contract.start_date + timedelta(days=i)
            for i in range((contract.end_date - contract.start_date).days + 1)
        )
        if day.weekday() != 6
    ]


@transaction.atomic
def allocate_contract_slots(*, contract, actor=None):
    total_needed = int(contract.employee_count or 0)
    days = _working_days(contract)

    if not days:
        raise ValidationError("Khoảng thời gian hợp đồng không có ngày làm việc hợp lệ.")

    available_by_date = {}
    total_available = 0

    for day in days:
        used_am = (
            ScheduleSlot.objects
            .filter(date=day, shift="AM")
            .exclude(contract=contract)
            .aggregate(total=Sum("capacity"))
            .get("total") or 0
        )
        used_pm = (
            ScheduleSlot.objects
            .filter(date=day, shift="PM")
            .exclude(contract=contract)
            .aggregate(total=Sum("capacity"))
            .get("total") or 0
        )

        remaining_am = max(0, MAX_AM_LIMIT - used_am)
        remaining_pm = max(0, MAX_PM_LIMIT - used_pm)

        available_by_date[day] = {
            "am": remaining_am,
            "pm": remaining_pm,
        }
        total_available += (remaining_am + remaining_pm)

    min_required = len(days) * 2 * MIN_PER_SHIFT_WHEN_AVAILABLE
    if total_available < min_required:
        raise ValidationError(
            f"Khoảng thời gian {contract.start_date} → {contract.end_date} chỉ còn "
            f"{total_available} slot, không đủ tối thiểu để mở lịch cho toàn bộ khung khám."
        )

    daily_base = total_needed // len(days) if total_needed > 0 else 0
    remainder = total_needed % len(days) if total_needed > 0 else 0

    for day in days:
        expected_today = daily_base + (1 if remainder > 0 else 0)
        if remainder > 0:
            remainder -= 1

        am_target = expected_today // 2 + (expected_today % 2)
        pm_target = expected_today // 2

        am_available = available_by_date[day]["am"]
        pm_available = available_by_date[day]["pm"]

        if am_target >= MIN_PER_SHIFT_WHEN_AVAILABLE and am_available >= am_target:
            am_assign = am_target
        elif am_available >= MIN_PER_SHIFT_WHEN_AVAILABLE:
            am_assign = MIN_PER_SHIFT_WHEN_AVAILABLE
        else:
            am_assign = min(am_target, am_available)

        if pm_target >= MIN_PER_SHIFT_WHEN_AVAILABLE and pm_available >= pm_target:
            pm_assign = pm_target
        elif pm_available >= MIN_PER_SHIFT_WHEN_AVAILABLE:
            pm_assign = MIN_PER_SHIFT_WHEN_AVAILABLE
        else:
            pm_assign = min(pm_target, pm_available)

        schedule_am = (
            ScheduleSlot.objects
            .select_for_update()
            .filter(contract=contract, date=day, shift="AM", slot_type=SlotType.CONTRACT)
            .first()
        )
        if schedule_am:
            new_capacity = max(am_assign, schedule_am.booked_count or 0)
            if schedule_am.capacity != new_capacity:
                schedule_am.capacity = new_capacity
                schedule_am.save(update_fields=["capacity", "updated_at"])
        elif am_assign > 0:
            ScheduleSlot.objects.create(
                contract=contract,
                date=day,
                shift="AM",
                slot_type=SlotType.CONTRACT,
                capacity=am_assign,
                booked_count=0,
            )

        schedule_pm = (
            ScheduleSlot.objects
            .select_for_update()
            .filter(contract=contract, date=day, shift="PM", slot_type=SlotType.CONTRACT)
            .first()
        )
        if schedule_pm:
            new_capacity = max(pm_assign, schedule_pm.booked_count or 0)
            if schedule_pm.capacity != new_capacity:
                schedule_pm.capacity = new_capacity
                schedule_pm.save(update_fields=["capacity", "updated_at"])
        elif pm_assign > 0:
            ScheduleSlot.objects.create(
                contract=contract,
                date=day,
                shift="PM",
                slot_type=SlotType.CONTRACT,
                capacity=pm_assign,
                booked_count=0,
            )

    stale_slots = (
        ScheduleSlot.objects
        .filter(contract=contract, slot_type=SlotType.CONTRACT)
        .exclude(date__in=days)
        .filter(booked_count=0)
    )
    stale_slots.delete()

    return contract