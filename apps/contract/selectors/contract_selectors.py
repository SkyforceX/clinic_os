from apps.contract.models.quotation import QuotationDraft
from apps.contract.policies import ContractPolicy
from apps.scheduling.models import ContractScheduleConfig, SlotType


def _get_schedule_rows_for_config(config):
    contract_profile = getattr(config, "contract", None)
    contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None

    if contract_obj:
        return list(
            contract_obj.schedule_slots.filter(
                slot_type=SlotType.CONTRACT,
            ).order_by("date", "shift", "id")
        )

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
            "contract__contract__implementation_plan",
            "registered_by",
        )
        .order_by("-updated_at", "-id")
    )

    if ContractPolicy.is_manager(user):
        return qs

    configs = list(qs if ContractPolicy.is_manager(user) else qs.filter(quotation__created_by=user))

    for config in configs:
        owner_user_id = getattr(getattr(config, "quotation", None), "created_by_id", None)
        config.can_delete = (
            not getattr(config, "contract_id", None)
            and (ContractPolicy.is_manager(user) or owner_user_id == user.id)
        )

    return configs


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