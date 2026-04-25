from apps.contract.models.quotation import QuotationDraft
from apps.contract.policies import ContractPolicy
from apps.scheduling.models import ContractScheduleConfig, SlotType
from apps.scheduling.policies import SchedulingPolicy


def _can_view_all_contract_data(user):
    return ContractPolicy.is_manager(user) or ContractPolicy.is_executive(user)


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

    if _can_view_all_contract_data(user):
        configs = list(qs)
    else:
        configs = list(qs.filter(quotation__created_by=user))

    for config in configs:
        owner_user_id = getattr(getattr(config, "quotation", None), "created_by_id", None)
        is_owner_or_manager = _can_view_all_contract_data(user) or owner_user_id == user.id
        config.can_delete = not getattr(config, "contract_id", None) and is_owner_or_manager
        config.can_confirm = not config.is_confirmed and is_owner_or_manager
        config.can_end = (
            config.is_confirmed
            and not config.is_ended
            and SchedulingPolicy.can_end_schedule(user, owner_user_id)
        )

    return configs


def list_quotations_for_schedule_user(user):
    qs = (
        QuotationDraft.objects.select_related("company", "created_by")
        .filter(company__isnull=False)
        .order_by("-created_at", "-id")
    )

    if _can_view_all_contract_data(user):
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

    if not _can_view_all_contract_data(user):
        qs = qs.filter(quotation__created_by=user)

    config = qs.first()
    if not config:
        return None

    config.blood_collection_rows_list = list(
        config.blood_collection_rows.all().order_by("collection_date", "id")
    )
    config.schedule_rows = _get_schedule_rows_for_config(config)
    return config
