from django.db import transaction

from apps.contract.domain.exceptions import ContractPermissionDenied, ContractValidationError
from apps.contract.models import BloodCollectionSchedule, Contract, ContractServiceLine
from apps.contract.policies import ContractPolicy
from apps.scheduling.models import ScheduleSlot


@transaction.atomic
def execute(*, contract: Contract, actor) -> None:
    if not contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    locked_contract = Contract.objects.select_for_update().filter(pk=contract.pk).first()
    if not locked_contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    if not ContractPolicy.can_delete(actor, locked_contract):
        raise ContractPermissionDenied("Bạn không có quyền xóa hợp đồng này.")

    ScheduleSlot.objects.filter(contract_id=locked_contract.id).delete()
    BloodCollectionSchedule.objects.filter(contract_id=locked_contract.id).delete()
    ContractServiceLine.objects.filter(contract_id=locked_contract.id).delete()

    if hasattr(locked_contract, "corporate_profile"):
        try:
            locked_contract.corporate_profile.delete()
        except Exception:
            pass

    locked_contract.delete()