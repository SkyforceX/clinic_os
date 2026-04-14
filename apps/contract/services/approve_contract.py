from django.db import transaction
from django.utils import timezone

from apps.contract.domain.exceptions import ContractPermissionDenied, ContractValidationError
from apps.contract.models import Contract
from apps.contract.models.contract import ContractStatus
from apps.contract.policies import ContractPolicy


@transaction.atomic
def execute(*, contract: Contract, actor) -> Contract:
    if not contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    locked_contract = Contract.objects.select_for_update().filter(pk=contract.pk).first()
    if not locked_contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    if not ContractPolicy.can_approve(actor, locked_contract):
        raise ContractPermissionDenied("Bạn không có quyền duyệt hợp đồng.")

    if locked_contract.is_approved:
        raise ContractValidationError("Hợp đồng đã được duyệt trước đó.")

    locked_contract.status = ContractStatus.APPROVED
    locked_contract.approved_by = actor
    locked_contract.approved_at = timezone.now()
    locked_contract.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return locked_contract