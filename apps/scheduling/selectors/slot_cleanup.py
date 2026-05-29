from collections import defaultdict

from django.core.exceptions import ValidationError

from apps.booking.models import Appointment
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_matrix import (
    _appointment_patient,
    _display_user_name,
    _get_company_name_from_config,
)


def _slot_owner_filter(config):
    contract_profile = getattr(config, "contract", None)
    contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None
    if contract_obj:
        return {"contract_id": contract_obj.id, "slot_type": SlotType.CONTRACT}
    return {
        "quotation_id": config.quotation_id,
        "contract_id__isnull": True,
        "slot_type": SlotType.CONTRACT,
    }


def _patient_payload(appointment):
    patient = _appointment_patient(appointment)
    return {
        "appointment_id": appointment.id,
        "shift": appointment.schedule_slot.get_shift_display(),
        "shift_code": appointment.schedule_slot.shift,
        "patient_code": (
            getattr(patient, "ma_bn", "")
            or getattr(patient, "his_patient_code", "")
            or ""
        ),
        "name": (
            getattr(patient, "ho_ten", "")
            or getattr(patient, "full_name", "")
            or str(patient or "")
        ),
        "dob": (
            getattr(patient, "birth_date_display", "")
            or (
                getattr(patient, "ngay_sinh", None).strftime("%d/%m/%Y")
                if getattr(patient, "ngay_sinh", None)
                else ""
            )
        ),
        "status": appointment.get_status_display(),
    }


def get_slot_cleanup_modal_payload(*, actor, config_id):
    if not SchedulingPolicy.can_cleanup_slot_registrations(actor):
        raise PermissionError("Ban khong co quyen xoa dang ky slot.")

    config = (
        ContractScheduleConfig.objects.select_related(
            "quotation",
            "quotation__created_by",
            "contract",
            "contract__contract",
            "registered_by",
        )
        .filter(pk=config_id)
        .first()
    )
    if not config:
        raise ValidationError("Khong tim thay lich kham.")

    slots = list(
        ScheduleSlot.objects.filter(**_slot_owner_filter(config))
        .order_by("date", "shift", "id")
        .values_list("id", flat=True)
    )

    appointments = (
        Appointment.objects.select_related(
            "schedule_slot",
            "patient",
            "his_patient_sync",
        )
        .filter(schedule_slot_id__in=slots)
        .order_by("schedule_slot__date", "schedule_slot__shift", "id")
    )

    by_date = defaultdict(list)
    for appointment in appointments:
        slot_date = appointment.schedule_slot.date
        by_date[slot_date].append(_patient_payload(appointment))

    day_entries = [
        {
            "date": day.isoformat(),
            "date_display": day.strftime("%d/%m/%Y"),
            "registrations": registrations,
        }
        for day, registrations in sorted(by_date.items())
    ]

    creator = getattr(config, "registered_by", None)
    return {
        "config_id": config.id,
        "company_name": _get_company_name_from_config(config) or "Lich kham doanh nghiep",
        "schedule_creator_name": _display_user_name(creator),
        "days": day_entries,
        "total_registrations": sum(len(item["registrations"]) for item in day_entries),
    }
