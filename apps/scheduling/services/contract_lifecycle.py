from django.core.exceptions import ValidationError
from django.db import transaction

from apps.booking.models import Appointment
from apps.contract.models import BloodCollectionSchedule
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_selectors import get_contract_for_actor
from apps.scheduling.services.allocate_slots import allocate_contract_slots


def redistribute_contract_slots(*, actor, contract_id):
    contract = get_contract_for_actor(user=actor, contract_id=contract_id)
    if not contract:
        raise ValueError("Không tìm thấy hợp đồng.")

    if not SchedulingPolicy.can_redistribute_slots(actor, contract):
        raise PermissionError("Bạn không có quyền phân bổ lại slot cho hợp đồng này.")

    return allocate_contract_slots(contract=contract, actor=actor)


@transaction.atomic
def delete_quote_schedule_config(*, actor, config_id):
    config = (
        ContractScheduleConfig.objects.select_for_update()
        .select_related("quotation", "quotation__created_by", "contract")
        .filter(pk=config_id)
        .first()
    )
    if not config:
        raise ValidationError("Không tìm thấy lịch đăng ký khám.")

    owner_user_id = getattr(config.quotation, "created_by_id", None)
    if not SchedulingPolicy.can_manage_quote_schedule(actor, owner_user_id):
        raise PermissionError("Bạn không có quyền xóa lịch đăng ký khám này.")

    if config.contract_id:
        raise ValidationError(
            "Lịch đăng ký khám này đã gắn với hợp đồng, không thể xóa từ màn hình đăng ký lịch."
        )

    quote_slots_qs = ScheduleSlot.objects.select_for_update().filter(
        quotation_id=config.quotation_id,
        contract__isnull=True,
        slot_type=SlotType.CONTRACT,
    )

    has_appointments = Appointment.objects.filter(schedule_slot__in=quote_slots_qs).exists()
    if has_appointments:
        raise ValidationError(
            "Lịch đăng ký khám đã có khách hàng đặt slot, không thể xóa."
        )

    quote_slots_qs.delete()
    BloodCollectionSchedule.objects.filter(contract__isnull=True).none().delete()
    config.delete()
    return True