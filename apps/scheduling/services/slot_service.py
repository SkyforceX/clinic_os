from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.scheduling.models import ScheduleSlot, SlotStatus, SlotType, TimeShift


@dataclass(frozen=True)
class SlotPayload:
    date: date
    shift: str
    capacity: int
    slot_type: str = SlotType.INDIVIDUAL
    contract_id: Optional[int] = None
    status: str = SlotStatus.OPEN
    note: str = ""


def daterange(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def validate_slot_payload(payload: SlotPayload) -> None:
    if payload.capacity < 0:
        raise ValidationError("capacity không được âm.")

    if payload.shift not in {TimeShift.MORNING, TimeShift.AFTERNOON}:
        raise ValidationError("shift không hợp lệ.")

    if payload.slot_type not in {SlotType.INDIVIDUAL, SlotType.CONTRACT}:
        raise ValidationError("slot_type không hợp lệ.")

    if payload.status not in {SlotStatus.OPEN, SlotStatus.CLOSED, SlotStatus.CANCELLED}:
        raise ValidationError("status không hợp lệ.")

    if payload.slot_type == SlotType.CONTRACT and not payload.contract_id:
        raise ValidationError("slot_type=CONTRACT bắt buộc có contract_id.")

    if payload.slot_type == SlotType.INDIVIDUAL and payload.contract_id:
        raise ValidationError("slot_type=INDIVIDUAL không được có contract_id.")


@transaction.atomic
def create_or_update_slot(
    *,
    slot_date: date,
    shift: str,
    capacity: int,
    slot_type: str = SlotType.INDIVIDUAL,
    contract_id: Optional[int] = None,
    status: str = SlotStatus.OPEN,
    note: str = "",
) -> ScheduleSlot:
    payload = SlotPayload(
        date=slot_date,
        shift=shift,
        capacity=capacity,
        slot_type=slot_type,
        contract_id=contract_id,
        status=status,
        note=note,
    )
    validate_slot_payload(payload)

    slot, created = ScheduleSlot.objects.select_for_update().get_or_create(
        date=payload.date,
        shift=payload.shift,
        slot_type=payload.slot_type,
        contract_id=payload.contract_id,
        defaults={
            "capacity": payload.capacity,
            "status": payload.status,
            "note": payload.note,
        },
    )

    if not created:
        if payload.capacity < slot.booked_count:
            raise ValidationError(
                f"Không thể giảm capacity xuống {payload.capacity} vì slot đã có "
                f"{slot.booked_count} đăng ký."
            )

        slot.capacity = payload.capacity
        slot.status = payload.status
        slot.note = payload.note
        slot.save(update_fields=["capacity", "status", "note", "updated_at"])

    return slot


@transaction.atomic
def bulk_create_or_update_slots(payloads: List[SlotPayload]) -> List[ScheduleSlot]:
    slots: List[ScheduleSlot] = []
    for payload in payloads:
        slot = create_or_update_slot(
            slot_date=payload.date,
            shift=payload.shift,
            capacity=payload.capacity,
            slot_type=payload.slot_type,
            contract_id=payload.contract_id,
            status=payload.status,
            note=payload.note,
        )
        slots.append(slot)
    return slots


@transaction.atomic
def create_individual_slots_for_date_range(
    *,
    start_date: date,
    end_date: date,
    am_capacity: int = 0,
    pm_capacity: int = 0,
    status: str = SlotStatus.OPEN,
    note: str = "",
) -> List[ScheduleSlot]:
    if start_date > end_date:
        raise ValidationError("start_date phải nhỏ hơn hoặc bằng end_date.")

    payloads: List[SlotPayload] = []
    for day in daterange(start_date, end_date):
        if am_capacity > 0:
            payloads.append(
                SlotPayload(
                    date=day,
                    shift=TimeShift.MORNING,
                    capacity=am_capacity,
                    slot_type=SlotType.INDIVIDUAL,
                    status=status,
                    note=note,
                )
            )
        if pm_capacity > 0:
            payloads.append(
                SlotPayload(
                    date=day,
                    shift=TimeShift.AFTERNOON,
                    capacity=pm_capacity,
                    slot_type=SlotType.INDIVIDUAL,
                    status=status,
                    note=note,
                )
            )

    return bulk_create_or_update_slots(payloads)


@transaction.atomic
def create_contract_slots_for_date_range(
    *,
    contract_id: int,
    start_date: date,
    end_date: date,
    am_capacity: int = 0,
    pm_capacity: int = 0,
    status: str = SlotStatus.OPEN,
    note: str = "",
) -> List[ScheduleSlot]:
    if start_date > end_date:
        raise ValidationError("start_date phải nhỏ hơn hoặc bằng end_date.")
    if not contract_id:
        raise ValidationError("contract_id là bắt buộc.")

    payloads: List[SlotPayload] = []
    for day in daterange(start_date, end_date):
        if am_capacity > 0:
            payloads.append(
                SlotPayload(
                    date=day,
                    shift=TimeShift.MORNING,
                    capacity=am_capacity,
                    slot_type=SlotType.CONTRACT,
                    contract_id=contract_id,
                    status=status,
                    note=note,
                )
            )
        if pm_capacity > 0:
            payloads.append(
                SlotPayload(
                    date=day,
                    shift=TimeShift.AFTERNOON,
                    capacity=pm_capacity,
                    slot_type=SlotType.CONTRACT,
                    contract_id=contract_id,
                    status=status,
                    note=note,
                )
            )

    return bulk_create_or_update_slots(payloads)


@transaction.atomic
def close_slot(slot_id: int) -> ScheduleSlot:
    slot = ScheduleSlot.objects.select_for_update().get(pk=slot_id)
    slot.status = SlotStatus.CLOSED
    slot.save(update_fields=["status", "updated_at"])