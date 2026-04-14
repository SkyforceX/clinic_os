from django.db import transaction

from apps.contract.domain.exceptions import ContractPermissionDenied, ContractValidationError
from apps.contract.models import BloodCollectionSchedule, Contract, ContractServiceLine
from apps.contract.policies import ContractPolicy
from apps.scheduling.models import ScheduleSlot


@transaction.atomic
def execute(*, contract: Contract, actor) -> None:
    if not contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    locked_contract = (
        Contract.objects
        .select_for_update()
        .select_related("corporate_profile", "corporate_profile__quotation")
        .filter(pk=contract.pk)
        .first()
    )
    if not locked_contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    if not ContractPolicy.can_delete(actor, locked_contract):
        raise ContractPermissionDenied("Bạn không có quyền xóa hợp đồng này.")

    profile = getattr(locked_contract, "corporate_profile", None)
    quotation = getattr(profile, "quotation", None) if profile else None

    # Reset trạng thái báo giá gốc
    if quotation:
        quotation.is_locked = False
        quotation.locked_at = None
        quotation.locked_by = None
        quotation.save(update_fields=["is_locked", "locked_at", "locked_by", "updated_at"])

    # Gỡ liên kết trước khi xóa để tránh báo giá còn bị xem là đã phát sinh hợp đồng
    if profile and quotation:
        profile.quotation = None
        profile.save(update_fields=["quotation", "updated_at"])

    ScheduleSlot.objects.filter(contract_id=locked_contract.id).delete()
    BloodCollectionSchedule.objects.filter(contract_id=locked_contract.id).delete()
    ContractServiceLine.objects.filter(contract_id=locked_contract.id).delete()

    if profile:
        try:
            profile.delete()
        except Exception:
            pass

    locked_contract.delete()