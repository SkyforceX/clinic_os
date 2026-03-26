from datetime import timedelta

from django.utils import timezone

from apps.contract.models import BloodCollectionSchedule, Contract
from apps.contract.models.contract import CLOSED_STATUSES
from apps.contract.policies import ContractPolicy
from apps.scheduling.models import ScheduleSlot


def contract_base_queryset():
    return (
        Contract.objects
        .select_related("company", "created_by")
        .prefetch_related("blood_collection_schedules", "schedule_slots")
        .all()
    )


def list_contracts_for_user(user):
    qs = contract_base_queryset()

    if ContractPolicy.is_manager(user):
        return qs.exclude(status__in=CLOSED_STATUSES).order_by("-created_at")

    today = timezone.now().date()
    expired_date = today - timedelta(days=21)

    return (
        qs.exclude(status__in=CLOSED_STATUSES)
        .filter(created_at__date__gt=expired_date, created_by=user)
        .order_by("-created_at")
    )


def get_contract_for_actor(*, user, contract_id):
    qs = contract_base_queryset()
    if ContractPolicy.is_manager(user):
        return qs.filter(id=contract_id).first()
    return qs.filter(id=contract_id, created_by=user).first()


def get_contract_detail(*, user, contract_id):
    contract = get_contract_for_actor(user=user, contract_id=contract_id)
    if not contract:
        return None

    contract.blood_collection_rows = list(
        BloodCollectionSchedule.objects.filter(contract_id=contract.id).order_by("collection_date", "id")
    )
    contract.schedule_rows = list(
        ScheduleSlot.objects.filter(contract_id=contract.id).order_by("date", "shift")
    )
    return contract


def get_contract_for_print(*, user, contract_id):
    return get_contract_detail(user=user, contract_id=contract_id)