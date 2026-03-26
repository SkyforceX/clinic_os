from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from apps.booking.models import Appointment
from apps.contract.models import Contract
from apps.scheduling.models import ScheduleSlot


class SchedulingRegistrationError(Exception):
    pass


@dataclass(frozen=True)
class RegistrationCommand:
    patient: object
    contract_id: int
    date_value: object
    shift_value: str


def _parse_date(value):
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value

    value = str(value or "").strip()
    if not value:
        raise SchedulingRegistrationError("Thiếu ngày khám.")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise SchedulingRegistrationError("Ngày khám không hợp lệ.")


def _normalize_shift(value):
    value = str(value or "").strip().lower()
    shift_map = {
        "am": "AM",
        "pm": "PM",
        "morning": "AM",
        "afternoon": "PM",
    }
    shift = shift_map.get(value)
    if not shift:
        raise SchedulingRegistrationError("Ca khám không hợp lệ.")
    return shift


@transaction.atomic
def register_or_move_patient_appointment(cmd: RegistrationCommand):
    contract = Contract.objects.filter(pk=cmd.contract_id).first()
    if not contract:
        raise SchedulingRegistrationError("Không tìm thấy hợp đồng khám sức khỏe.")

    target_date = _parse_date(cmd.date_value)
    target_shift = _normalize_shift(cmd.shift_value)

    schedule = (
        ScheduleSlot.objects.select_for_update()
        .filter(contract=contract, date=target_date, shift=target_shift)
        .first()
    )
    if not schedule:
        raise SchedulingRegistrationError("Không tìm thấy ca khám đã chọn.")

    if (schedule.booked_count or 0) >= (schedule.capacity or 0):
        raise SchedulingRegistrationError("Ca khám đã hết slot. Vui lòng chọn ca khác.")

    current_appointment = (
        Appointment.objects.select_for_update()
        .select_related("schedule_slot")
        .filter(patient=cmd.patient, schedule_slot__contract=contract)
        .first()
    )

    if current_appointment and current_appointment.schedule_slot_id == schedule.id:
        return {
            "appointment": current_appointment,
            "schedule": schedule,
            "is_update": False,
            "is_same_slot": True,
        }

    if current_appointment:
        old_schedule = ScheduleSlot.objects.select_for_update().get(pk=current_appointment.schedule_slot_id)
        if old_schedule.booked_count > 0:
            old_schedule.booked_count -= 1
            old_schedule.save(update_fields=["booked_count", "updated_at"])

        schedule.booked_count = (schedule.booked_count or 0) + 1
        schedule.save(update_fields=["booked_count", "updated_at"])

        current_appointment.schedule_slot = schedule
        current_appointment.save(update_fields=["schedule_slot", "updated_at"])

        return {
            "appointment": current_appointment,
            "schedule": schedule,
            "is_update": True,
            "is_same_slot": False,
        }

    appointment = Appointment.objects.create(
        patient=cmd.patient,
        schedule_slot=schedule,
    )

    schedule.booked_count = (schedule.booked_count or 0) + 1
    schedule.save(update_fields=["booked_count", "updated_at"])

    return {
        "appointment": appointment,
        "schedule": schedule,
        "is_update": False,
        "is_same_slot": False,
    }