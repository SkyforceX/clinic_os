from apps.contract.models.quotation import QuotationDraft
from apps.contract.policies import ContractPolicy
from apps.his_integration.selectors import get_package_exam_record_stats
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
            "his_package",
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
        config.can_unconfirm = (
            config.is_confirmed
            and not config.is_ended
            and SchedulingPolicy.is_it_staff(user)
        )
        config.his_actual_total = None
        config.his_cancelled = 0
        config.slot_warning_level = ""
        config.slot_warning_message = ""

        his_package = getattr(config, "his_package", None)
        if his_package:
            stats = get_package_exam_record_stats(package=his_package)
            config.his_actual_total = stats.get("total", 0)
            config.his_cancelled = stats.get("cancelled", 0)

            planned_count = int(getattr(config, "planned_employee_count", 0) or 0)
            actual_total = int(config.his_actual_total or 0)
            if planned_count < actual_total:
                config.slot_warning_level = "danger"
                config.slot_warning_message = "Số slot khám nhỏ hơn số BN thực tế trong gói HIS"
            elif planned_count > actual_total:
                config.slot_warning_level = "warning"
                config.slot_warning_message = "Số slot khám lớn hơn số BN thực tế từ gói HIS"

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
