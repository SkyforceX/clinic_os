from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from apps.booking.models import Appointment
from apps.contract.models import Contract
from apps.his_integration.models import HisExamRecordSync
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot


class SchedulingRegistrationError(Exception):
    pass


@dataclass(frozen=True)
class RegistrationCommand:
    patient: object
    contract_id: int
    date_value: object
    shift_value: str
    schedule_config_id: int = None


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


def _parse_optional_int(value):
    try:
        return int(str(value or "").strip())
    except Exception:
        return None


def _actual_contract_from_config(config):
    profile = getattr(config, "contract", None)
    return getattr(profile, "contract", None) if profile else None


def _patient_can_use_schedule_config(*, patient, config):
    patient_code = str(getattr(patient, "ma_bn", "") or "").strip()
    if getattr(config, "his_package_id", None):
        return HisExamRecordSync.objects.filter(
            package_sync_id=config.his_package_id,
            is_active=True,
            patient_sync__his_patient_code__iexact=patient_code,
            patient_sync__is_active=True,
        ).exists()

    quotation_company_id = getattr(getattr(config, "quotation", None), "company_id", None)
    return bool(quotation_company_id and quotation_company_id == getattr(patient, "company_id", None))


def _appointment_patient_filter(patient):
    if getattr(patient, "his_patient_code", None):
        return {"his_patient_sync": patient}
    return {"patient": patient}


def _resolve_registration_owner(cmd: RegistrationCommand):
    schedule_config_id = _parse_optional_int(cmd.schedule_config_id)
    if schedule_config_id:
        config = (
            ContractScheduleConfig.objects
            .select_related("quotation", "contract", "contract__contract", "his_package")
            .filter(pk=schedule_config_id)
            .first()
        )
        if not config or not _patient_can_use_schedule_config(patient=cmd.patient, config=config):
            raise SchedulingRegistrationError("Bạn không có quyền đăng ký lịch khám này.")

        actual_contract = _actual_contract_from_config(config)
        return {
            "contract": actual_contract,
            "quotation": None if actual_contract else config.quotation,
            "config": config,
        }

    contract_id = _parse_optional_int(cmd.contract_id)
    contract = Contract.objects.filter(pk=contract_id).first()
    if not contract:
        raise SchedulingRegistrationError("Không tìm thấy hợp đồng khám sức khỏe.")

    return {"contract": contract, "quotation": None, "config": None}


@transaction.atomic
def register_or_move_patient_appointment(cmd: RegistrationCommand):
    owner = _resolve_registration_owner(cmd)
    contract = owner["contract"]
    quotation = owner["quotation"]

    target_date = _parse_date(cmd.date_value)
    target_shift = _normalize_shift(cmd.shift_value)

    schedule_filter = {
        "date": target_date,
        "shift": target_shift,
    }
    if contract:
        schedule_filter["contract"] = contract
    else:
        schedule_filter["contract__isnull"] = True
        schedule_filter["quotation"] = quotation

    schedule = ScheduleSlot.objects.select_for_update().filter(**schedule_filter).first()
    if not schedule:
        raise SchedulingRegistrationError("Không tìm thấy ca khám đã chọn.")

    if (schedule.booked_count or 0) >= (schedule.capacity or 0):
        raise SchedulingRegistrationError("Ca khám đã hết slot. Vui lòng chọn ca khác.")

    current_filter = _appointment_patient_filter(cmd.patient)
    if contract:
        current_filter["schedule_slot__contract"] = contract
    else:
        current_filter["schedule_slot__contract__isnull"] = True
        current_filter["schedule_slot__quotation"] = quotation

    current_appointment = (
        Appointment.objects.select_for_update()
        .select_related("schedule_slot")
        .filter(**current_filter)
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
        **_appointment_patient_filter(cmd.patient),
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
