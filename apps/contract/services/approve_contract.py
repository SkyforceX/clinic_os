from django.db import transaction
from django.utils import timezone

from apps.booking.models import HealthContract
from apps.contract.domain.exceptions import ContractPermissionDenied, ContractValidationError
from apps.contract.policies import ContractPolicy


@transaction.atomic
def execute(*, contract: HealthContract, actor) -> HealthContract:
    if not contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    locked_contract = HealthContract.objects.select_for_update().filter(pk=contract.pk).first()
    if not locked_contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    if not ContractPolicy.can_approve(actor, locked_contract):
        raise ContractPermissionDenied("Bạn không có quyền duyệt hợp đồng.")

    if getattr(locked_contract, "is_approved", False):
        raise ContractValidationError("Hợp đồng đã được duyệt trước đó.")

    locked_contract.is_approved = True

    update_fields = ["is_approved"]

    if hasattr(locked_contract, "approved_by"):
        locked_contract.approved_by = actor
        update_fields.append("approved_by")

    if hasattr(locked_contract, "approved_at"):
        locked_contract.approved_at = timezone.now()
        update_fields.append("approved_at")

    if hasattr(locked_contract, "updated_at"):
        update_fields.append("updated_at")

    locked_contract.save(update_fields=update_fields)
    return locked_contract