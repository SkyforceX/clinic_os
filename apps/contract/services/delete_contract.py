from django.db import transaction

from apps.booking.models import AppointmentSchedule, BloodCollectionInfo, ContractServiceDetail, HealthContract
from apps.contract.domain.exceptions import ContractPermissionDenied, ContractValidationError
from apps.contract.policies import ContractPolicy


@transaction.atomic
def execute(*, contract: HealthContract, actor) -> None:
    if not contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    locked_contract = HealthContract.objects.select_for_update().filter(pk=contract.pk).first()
    if not locked_contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    if not ContractPolicy.can_delete(actor, locked_contract):
        raise ContractPermissionDenied("Bạn không có quyền xóa hợp đồng này.")

    AppointmentSchedule.objects.filter(contract_id=locked_contract.id).delete()
    BloodCollectionInfo.objects.filter(contract_id=locked_contract.id).delete()
    ContractServiceDetail.objects.filter(contract_id=locked_contract.id).delete()

    if hasattr(locked_contract, "corporate_profile"):
        try:
            locked_contract.corporate_profile.delete()
        except Exception:
            pass

    locked_contract.delete()