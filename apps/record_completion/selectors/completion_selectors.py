"""
apps/record_completion/selectors/completion_selectors.py
"""

from datetime import date, timedelta

from django.db import models

from apps.his_integration.selectors import count_active_his_patients_for_organization
from apps.organizations.models import Company
from apps.reception.models import CheckInRecord, CheckInStatus
from apps.record_completion.models import (
    COMPLETED_STAGE,
    OVERDUE_DAYS,
    STEP_CONFIGS,
    TOTAL_STEPS,
    RecordCompletion,
)


def _company_checkin_qs(company: Company):
    return CheckInRecord.objects.filter(
        models.Q(company=company)
        | models.Q(company__isnull=True, snapshot_company_name=company.name)
    )


def ensure_completions_for_company(company: Company) -> None:
    checked_out_qs = _company_checkin_qs(company).filter(
        status=CheckInStatus.CHECKED_OUT,
    )
    existing_ids = set(
        RecordCompletion.objects.filter(
            checkin_record__company=company
        ).values_list("checkin_record_id", flat=True)
    )
    to_create = [
        RecordCompletion(checkin_record=rec, company=company)
        for rec in checked_out_qs
        if rec.pk not in existing_ids
    ]
    if to_create:
        RecordCompletion.objects.bulk_create(to_create, ignore_conflicts=True)


def get_checkin_stats_for_company(company: Company) -> dict:
    """
    total_patients, checked_in_count, deferred_count, not_checked_count
    """
    total_patients = count_active_his_patients_for_organization(organization_id=company.id)

    ci_qs = _company_checkin_qs(company)

    checked_in_bns = set(
        ci_qs.filter(
            status__in=[CheckInStatus.CHECKED_IN, CheckInStatus.CHECKED_OUT]
        ).values_list("snapshot_ma_bn", flat=True)
    )
    deferred_bns = set(
        ci_qs.filter(status=CheckInStatus.DEFERRED)
        .values_list("snapshot_ma_bn", flat=True)
    )

    checked_in_count  = len(checked_in_bns)
    deferred_count    = len(deferred_bns - checked_in_bns)
    not_checked_count = max(0, total_patients - checked_in_count - deferred_count)

    return {
        "total_patients":    total_patients,
        "checked_in_count":  checked_in_count,
        "deferred_count":    deferred_count,
        "not_checked_count": not_checked_count,
    }


def get_active_companies_summary():
    overdue_threshold = date.today() - timedelta(days=OVERDUE_DAYS)

    checked_out_qs = CheckInRecord.objects.filter(status=CheckInStatus.CHECKED_OUT)
    checked_out_ids = set(
        checked_out_qs.exclude(company_id__isnull=True)
        .values_list("company_id", flat=True).distinct()
    )
    checked_out_names = set(
        checked_out_qs.filter(company_id__isnull=True)
        .exclude(snapshot_company_name="")
        .values_list("snapshot_company_name", flat=True).distinct()
    )
    incomplete_ids = set(
        RecordCompletion.objects.filter(is_completed=False)
        .values_list("company_id", flat=True).distinct()
    )
    all_ids = (checked_out_ids | incomplete_ids) - {None}

    if not all_ids and not checked_out_names:
        return []

    result = []
    companies = Company.objects.filter(
        models.Q(id__in=all_ids) | models.Q(name__in=checked_out_names)
    ).distinct().order_by("name")
    for company in companies:
        qs           = RecordCompletion.objects.filter(company=company)
        without_qs   = _company_checkin_qs(company).filter(
            status=CheckInStatus.CHECKED_OUT,
        ).exclude(record_completion__isnull=False)

        total         = qs.count() + without_qs.count()
        completed     = qs.filter(is_completed=True).count()
        overdue_count = qs.filter(
            is_completed=False,
            checkin_record__exam_date__lt=overdue_threshold,
        ).count()
        pct = int(completed / total * 100) if total > 0 else 0

        result.append({
            "company":       company,
            "total":         total,
            "completed":     completed,
            "pct":           pct,
            "overdue_count": overdue_count,
            **get_checkin_stats_for_company(company),
        })

    return result


def get_company_for_pipeline(company_id: int):
    return Company.objects.filter(id=company_id).first()


def get_pipeline_for_company(company: Company, ma_bn_filter: str = ""):
    qs = (
        RecordCompletion.objects
        .filter(company=company)
        .select_related("checkin_record")
        .order_by("checkin_record__exam_date", "checkin_record__snapshot_ho_ten")
    )
    if ma_bn_filter:
        qs = qs.filter(checkin_record__snapshot_ma_bn__icontains=ma_bn_filter)

    overdue_threshold = date.today() - timedelta(days=OVERDUE_DAYS)
    all_records       = list(qs)

    buckets = {i: [] for i in range(TOTAL_STEPS + 1)}
    for rec in all_records:
        buckets[TOTAL_STEPS if rec.is_completed else rec.current_step].append(rec)

    stages = [
        {"config": cfg, "completions": buckets[cfg["index"]], "count": len(buckets[cfg["index"]])}
        for cfg in STEP_CONFIGS
    ]
    stages.append({
        "config": COMPLETED_STAGE,
        "completions": buckets[TOTAL_STEPS],
        "count": len(buckets[TOTAL_STEPS]),
    })

    total           = len(all_records)
    completed_count = len(buckets[TOTAL_STEPS])
    overdue_count   = sum(
        1 for r in all_records
        if not r.is_completed and r.checkin_record.exam_date < overdue_threshold
    )

    return {
        "stages":          stages,
        "total":           total,
        "completed_count": completed_count,
        "overdue_count":   overdue_count,
        "pct":             int(completed_count / total * 100) if total > 0 else 0,
    }


def get_completion_with_logs(completion_id: int):
    try:
        rc   = RecordCompletion.objects.select_related("checkin_record", "company").get(pk=completion_id)
        logs = list(rc.logs.select_related("actor").order_by("step", "confirmed_at"))
        return rc, logs
    except RecordCompletion.DoesNotExist:
        return None, []
