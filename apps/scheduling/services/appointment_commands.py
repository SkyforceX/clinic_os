from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from apps.contract.models import Contract
from apps.scheduling.models import Appointment, ScheduleSlot


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


def _registered_field_name(schedule):
    return "registered_am" if schedule.shift == "AM" else "registered_pm"


def _limit_value(schedule):
    return schedule.limit_am if schedule.shift == "AM" else schedule.limit_pm


def _registered_value(schedule):
    field_name = _registered_field_name(schedule)
    real_count = schedule.appointments.count()
    return max(getattr(schedule, field_name) or 0, real_count)


def _sync_registered(schedule):
    field_name = _registered_field_name(schedule)
    current_value = _registered_value(schedule)
    if getattr(schedule, field_name) != current_value:
        setattr(schedule, field_name, current_value)
        schedule.save(update_fields=[field_name, "updated_at"])
    return current_value


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

    registered_now = _sync_registered(schedule)
    limit_now = _limit_value(schedule)

    current_appointment = (
        Appointment.objects.select_for_update()
        .select_related("schedule")
        .filter(patient=cmd.patient, schedule__contract=contract)
        .first()
    )

    if current_appointment and current_appointment.schedule_id == schedule.id:
        return {
            "appointment": current_appointment,
            "schedule": schedule,
            "is_update": False,
            "is_same_slot": True,
        }

    if registered_now >= limit_now:
        raise SchedulingRegistrationError("Ca khám đã hết slot. Vui lòng chọn ca khác.")

    if current_appointment:
        old_schedule = ScheduleSlot.objects.select_for_update().get(pk=current_appointment.schedule_id)
        old_field = _registered_field_name(old_schedule)
        old_value = max(0, _registered_value(old_schedule) - 1)
        setattr(old_schedule, old_field, old_value)
        old_schedule.save(update_fields=[old_field, "updated_at"])

        new_field = _registered_field_name(schedule)
        setattr(schedule, new_field, registered_now + 1)
        schedule.save(update_fields=[new_field, "updated_at"])

        current_appointment.schedule = schedule
        current_appointment.save(update_fields=["schedule", "updated_at"])

        return {
            "appointment": current_appointment,
            "schedule": schedule,
            "is_update": True,
            "is_same_slot": False,
        }

    appointment = Appointment.objects.create(
        patient=cmd.patient,
        schedule=schedule,
    )

    field_name = _registered_field_name(schedule)
    setattr(schedule, field_name, registered_now + 1)
    schedule.save(update_fields=[field_name, "updated_at"])

    return {
        "appointment": appointment,
        "schedule": schedule,
        "is_update": False,
        "is_same_slot": False,
    }