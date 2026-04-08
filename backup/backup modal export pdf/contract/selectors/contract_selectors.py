from apps.contract.models.quotation import QuotationDraft
from apps.contract.policies import ContractPolicy
from apps.scheduling.models import ContractScheduleConfig, SlotType


def _get_schedule_rows_for_config(config):
    if config.contract_id:
        contract_slots = list(
            config.contract.schedule_slots.filter(
                slot_type=SlotType.CONTRACT,
            ).order_by("date", "shift", "id")
        )
        if contract_slots:
            return contract_slots

    if config.quotation_id:
        return list(
            config.quotation.schedule_slots.filter(
                slot_type=SlotType.CONTRACT,
            ).order_by("date", "shift", "id")
        )

    return []


def list_schedule_configs_for_user(user):
    qs = (
        ContractScheduleConfig.objects.select_related(
            "quotation",
            "quotation__company",
            "quotation__created_by",
            "contract",
            "contract__contract",
            "registered_by",
        )
        .order_by("-updated_at", "-id")
    )

    if ContractPolicy.is_manager(user):
        return qs

    return qs.filter(quotation__created_by=user)


def list_quotations_for_schedule_user(user):
    qs = (
        QuotationDraft.objects.select_related("company", "created_by")
        .filter(company__isnull=False)
        .order_by("-created_at", "-id")
    )

    if ContractPolicy.is_manager(user):
        return qs

    return qs.filter(created_by=user)


def get_schedule_config_detail_for_user(*, user, config_id):
    qs = (
        ContractScheduleConfig.objects.select_related(
            "quotation",
            "quotation__company",
            "quotation__created_by",
            "contract",
            "contract__contract",
            "registered_by",
        )
        .prefetch_related("blood_collection_rows")
        .filter(pk=config_id)
    )

    if not ContractPolicy.is_manager(user):
        qs = qs.filter(quotation__created_by=user)

    config = qs.first()
    if not config:
        return None

    config.blood_collection_rows_list = list(
        config.blood_collection_rows.all().order_by("collection_date", "id")
    )
    config.schedule_rows = _get_schedule_rows_for_config(config)
    return config