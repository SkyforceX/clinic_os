from __future__ import annotations

from dataclasses import dataclass

from apps.his_integration.selectors import list_active_schedule_configs_for_his_patient
from apps.reception.models import CheckInRecord


UNKNOWN_COMPANY_NAMES = {
    "",
    "không xác định",
    "khong xac dinh",
    "unknown",
}


def _normalize_company_name(value) -> str:
    return (value or "").strip()


def _is_unknown_company_name(value) -> bool:
    normalized = _normalize_company_name(value).lower()
    return normalized in UNKNOWN_COMPANY_NAMES


def _resolve_company_context_from_schedule(schedule_config):
    his_package = getattr(schedule_config, "his_package", None) if schedule_config else None
    company = getattr(his_package, "organization", None) if his_package else None
    company_name = (
        getattr(his_package, "company_name", "")
        or getattr(company, "name", "")
    )
    return {
        "schedule_config": schedule_config,
        "company": company,
        "company_name": _normalize_company_name(company_name),
        "exam_start": getattr(schedule_config, "exam_start_date", None) if schedule_config else None,
        "exam_end": getattr(schedule_config, "exam_end_date", None) if schedule_config else None,
    }


def _resolve_schedule_config_for_record(record, cache: dict[str, object]):
    if getattr(record, "schedule_config_id", None):
        return record.schedule_config

    patient_code = (
        getattr(getattr(record, "his_patient_sync", None), "his_patient_code", "")
        or record.snapshot_ma_bn
    )
    patient_code = (patient_code or "").strip().upper()
    if not patient_code:
        return None

    if patient_code not in cache:
        cache[patient_code] = list(
            list_active_schedule_configs_for_his_patient(patient_code=patient_code)
        )

    configs = cache[patient_code]
    if not configs:
        return None

    for config in configs:
        start_date = getattr(config, "exam_start_date", None)
        end_date = getattr(config, "exam_end_date", None)
        if start_date and end_date and start_date <= record.exam_date <= end_date:
            return config

    return sorted(
        configs,
        key=lambda cfg: (
            getattr(cfg, "exam_end_date", None) or record.exam_date,
            getattr(cfg, "id", 0),
        ),
        reverse=True,
    )[0]


@dataclass
class BackfillResult:
    scanned: int = 0
    updated: int = 0
    unchanged: int = 0
    unresolved: int = 0
    unresolved_details: list[dict] | None = None


def backfill_checkin_company_data(*, queryset, dry_run: bool = False, force_all: bool = False):
    result = BackfillResult(unresolved_details=[])
    schedule_cache: dict[str, object] = {}

    records = queryset.select_related(
        "his_patient_sync",
        "company",
        "schedule_config",
        "schedule_config__his_package",
        "schedule_config__his_package__organization",
    ).order_by("id")

    for record in records.iterator():
        result.scanned += 1

        should_refresh_name = force_all or _is_unknown_company_name(record.snapshot_company_name)
        if not should_refresh_name and record.company_id and record.schedule_config_id:
            result.unchanged += 1
            continue

        schedule_config = _resolve_schedule_config_for_record(record, schedule_cache)
        context = _resolve_company_context_from_schedule(schedule_config)
        company_name = context["company_name"]
        company = context["company"]

        if not company_name:
            result.unresolved += 1
            result.unresolved_details.append(
                {
                    "id": record.id,
                    "patient_code": (record.snapshot_ma_bn or "").strip(),
                    "exam_date": str(record.exam_date),
                    "his_patient_sync_id": record.his_patient_sync_id,
                    "schedule_config_id": record.schedule_config_id,
                    "company_id": record.company_id,
                }
            )
            continue

        update_fields = []
        if should_refresh_name and record.snapshot_company_name != company_name:
            record.snapshot_company_name = company_name
            update_fields.append("snapshot_company_name")

        if schedule_config and record.schedule_config_id != getattr(schedule_config, "id", None):
            record.schedule_config = schedule_config
            update_fields.append("schedule_config")

        if company and record.company_id != getattr(company, "id", None):
            record.company = company
            update_fields.append("company")

        if not record.snapshot_exam_start and context["exam_start"]:
            record.snapshot_exam_start = context["exam_start"]
            update_fields.append("snapshot_exam_start")

        if not record.snapshot_exam_end and context["exam_end"]:
            record.snapshot_exam_end = context["exam_end"]
            update_fields.append("snapshot_exam_end")

        if not update_fields:
            result.unchanged += 1
            continue

        if not dry_run:
            record.save(update_fields=update_fields + ["updated_at"])
        result.updated += 1

    return result
