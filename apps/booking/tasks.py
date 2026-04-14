from datetime import timedelta

from background_task import background
from django.utils import timezone

from apps.contract.models import Contract
from apps.contract.models.contract import ContractStatus


@background(schedule=60)
def auto_terminate_contracts():
    today = timezone.now().date()
    expired_date = today - timedelta(days=16)

    qs = Contract.objects.filter(
        status__in=[ContractStatus.SUBMITTED, ContractStatus.APPROVED, ContractStatus.ACTIVE],
        created_at__date__lte=expired_date,
    )

    updated = 0
    for contract in qs:
        contract.status = ContractStatus.TERMINATED
        contract.terminated_at = today
        contract.save(update_fields=["status", "terminated_at", "updated_at"])
        updated += 1

    print(f"Đã cập nhật {updated} hợp đồng hết hạn.")