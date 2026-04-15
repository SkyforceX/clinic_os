"""
apps/record_completion/selectors/completion_selectors.py
"""

from datetime import date, timedelta

from apps.organizations.models import Company
from apps.patients.models import Patient
from apps.reception.models import CheckInRecord, CheckInStatus
from apps.record_completion.models import (
    COMPLETED_STAGE,
    OVERDUE_DAYS,
    STEP_CONFIGS,
    TOTAL_STEPS,
    RecordCompletion,
)


def ensure_completions_for_company(company: Company) -> None:
    checked_out_qs = CheckInRecord.objects.filter(
        company=company,
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
    total_patients = Patient.objects.filter(company=company).count()

    ci_qs = CheckInRecord.objects.filter(company=company)

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

    checked_out_ids = set(
        CheckInRecord.objects.filter(status=CheckInStatus.CHECKED_OUT)
        .values_list("company_id", flat=True).distinct()
    )
    incomplete_ids = set(
        RecordCompletion.objects.filter(is_completed=False)
        .values_list("company_id", flat=True).distinct()
    )
    all_ids = (checked_out_ids | incomplete_ids) - {None}

    if not all_ids:
        return []

    result = []
    for company in Company.objects.filter(id__in=all_ids).order_by("name"):
        qs           = RecordCompletion.objects.filter(company=company)
        without_qs   = CheckInRecord.objects.filter(
            company=company, status=CheckInStatus.CHECKED_OUT,
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
