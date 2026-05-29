from django.core.exceptions import ValidationError
from django.db import transaction

from apps.booking.models import Appointment
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType
from apps.scheduling.policies import SchedulingPolicy


def _config_for_slot(slot):
    if slot.contract_id:
        return (
            ContractScheduleConfig.objects
            .filter(contract__contract_id=slot.contract_id)
            .first()
        )
    if slot.quotation_id:
        return ContractScheduleConfig.objects.filter(quotation_id=slot.quotation_id).first()
    return None


@transaction.atomic
def delete_slot_registration(*, actor, appointment_id):
    if not SchedulingPolicy.can_cleanup_slot_registrations(actor):
        raise PermissionError("Ban khong co quyen xoa dang ky slot.")

    appointment = (
        # his_patient_sync là FK nullable; khóa chỉ row Appointment để tránh
        # PostgreSQL báo lỗi FOR UPDATE trên outer join do select_related().
        Appointment.objects.select_for_update(of=("self",))
        .select_related("schedule_slot", "patient", "his_patient_sync")
        .filter(pk=appointment_id)
        .first()
    )
    if not appointment:
        raise ValidationError("Khong tim thay dang ky slot.")

    slot = (
        ScheduleSlot.objects.select_for_update()
        .filter(pk=appointment.schedule_slot_id)
        .first()
    )
    if not slot or slot.slot_type != SlotType.CONTRACT:
        raise ValidationError("Chi ho tro xoa dang ky tren slot hop dong.")

    config = _config_for_slot(slot)
    patient = appointment.his_patient_sync or appointment.patient
    patient_name = (
        getattr(patient, "ho_ten", "")
        or getattr(patient, "full_name", "")
        or str(patient or "")
    )

    appointment.delete()

    remaining_count = Appointment.objects.filter(schedule_slot_id=slot.id).count()
    if slot.booked_count != remaining_count:
        slot.booked_count = remaining_count
        slot.save(update_fields=["booked_count", "updated_at"])

    return {
        "config_id": getattr(config, "id", None),
        "slot_id": slot.id,
        "remaining_count": remaining_count,
        "patient_name": patient_name,
    }
