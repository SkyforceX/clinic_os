from django.db import transaction

from apps.his_integration.selectors import (
    get_active_corporate_package_by_id,
    get_contract_available_for_his_package_link,
    get_schedule_config_available_for_his_package_link,
)


class HisPackageLinkingError(ValueError):
    pass


@transaction.atomic
def link_contract_to_his_package(*, package_id, contract_id, actor=None):
    package = get_active_corporate_package_by_id(package_id=package_id)
    if not package:
        raise HisPackageLinkingError("Không tìm thấy gói khám HIS.")

    contract = get_contract_available_for_his_package_link(
        package=package,
        contract_id=contract_id,
    )
    if not contract:
        raise HisPackageLinkingError(
            "Hợp đồng không hợp lệ hoặc đã liên kết với gói khám khác."
        )

    update_fields = []
    if package.contract_id != contract.id:
        package.contract = contract
        update_fields.append("contract")

    if not package.organization_id and getattr(contract, "company_id", None):
        package.organization_id = contract.company_id
        update_fields.append("organization")

    if update_fields:
        package.save(update_fields=update_fields)

    return package


@transaction.atomic
def link_schedule_config_to_his_package(*, package_id, schedule_config_id, actor=None):
    package = get_active_corporate_package_by_id(package_id=package_id)
    if not package:
        raise HisPackageLinkingError("Không tìm thấy gói khám HIS.")

    schedule_config = get_schedule_config_available_for_his_package_link(
        package=package,
        schedule_config_id=schedule_config_id,
    )
    if not schedule_config:
        raise HisPackageLinkingError(
            "Lịch khám không hợp lệ hoặc đã liên kết với gói khám khác."
        )

    if schedule_config.his_package_id != package.id:
        schedule_config.his_package = package
        schedule_config.save(update_fields=["his_package", "updated_at"])

    if not package.organization_id:
        company_id = getattr(getattr(schedule_config, "quotation", None), "company_id", None)
        if company_id:
            package.organization_id = company_id
            package.save(update_fields=["organization"])

    return schedule_config


@transaction.atomic
def unlink_schedule_config_from_his_package(*, package_id, schedule_config_id, actor=None):
    package = get_active_corporate_package_by_id(package_id=package_id)
    if not package:
        raise HisPackageLinkingError("Không tìm thấy gói khám HIS.")

    try:
        schedule_config = package.schedule_configs.get(pk=schedule_config_id)
    except Exception:
        raise HisPackageLinkingError("Lịch khám không thuộc gói khám này.")

    schedule_config.his_package = None
    schedule_config.save(update_fields=["his_package", "updated_at"])
    return schedule_config
