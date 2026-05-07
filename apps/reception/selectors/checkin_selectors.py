"""
apps/reception/selectors/checkin_selectors.py
===============================================
Truy vấn dữ liệu check-in cho sidebar thống kê.
"""

from datetime import date

from apps.his_integration.selectors import list_active_schedule_configs_for_his_patient
from apps.reception.models import CheckInRecord, CheckInStatus


def _resolve_his_company_name_for_record(record):
    schedule_config = getattr(record, "schedule_config", None)
    his_package = getattr(schedule_config, "his_package", None) if schedule_config else None
    company_name = (
        getattr(his_package, "company_name", "")
        or getattr(getattr(his_package, "organization", None), "name", "")
    )
    return (company_name or "").strip()


def _resolve_his_company_name_for_patient_code(*, patient_code, exam_date=None, cache=None):
    normalized_code = (patient_code or "").strip().upper()
    if not normalized_code:
        return ""

    cache = cache if cache is not None else {}
    cache_key = (normalized_code, exam_date.isoformat() if exam_date else "")
    if cache_key in cache:
        return cache[cache_key]

    schedule_configs = list(
        list_active_schedule_configs_for_his_patient(patient_code=normalized_code)
    )
    target_config = None

    if exam_date:
        for cfg in schedule_configs:
            start_date = getattr(cfg, "exam_start_date", None)
            end_date = getattr(cfg, "exam_end_date", None)
            if start_date and end_date and start_date <= exam_date <= end_date:
                target_config = cfg
                break

    if target_config is None and schedule_configs:
        target_config = schedule_configs[0]

    if target_config is None:
        cache[cache_key] = ""
        return cache[cache_key]

    cache[cache_key] = _resolve_his_company_name_for_record(
        type("RecordLike", (), {"schedule_config": target_config})()
    )
    return cache[cache_key]


def get_checkin_record_company_name(record, cache=None):
    company_name = _resolve_his_company_name_for_record(record)
    if company_name:
        return company_name

    patient_code = (
        getattr(getattr(record, "his_patient_sync", None), "his_patient_code", "")
        or getattr(record, "snapshot_ma_bn", "")
    )
    return _resolve_his_company_name_for_patient_code(
        patient_code=patient_code,
        exam_date=getattr(record, "exam_date", None),
        cache=cache,
    )


def get_today_stats(exam_date: date = None):
    """
    Trả về thống kê check-in theo công ty trong ngày.
    Format:
    [
      {
        company_name: str,
        exam_start: date,
        exam_end: date,
        total_checkin: int,
        total_checkout: int,
        total_deferred: int,
        records: QuerySet
      },
      ...
    ]
    """
    exam_date = exam_date or date.today()

    records = (
        CheckInRecord.objects
        .filter(exam_date=exam_date)
        .select_related("his_patient_sync", "schedule_config", "schedule_config__his_package", "schedule_config__his_package__organization")
        .order_by("snapshot_company_name", "-checked_in_at")
    )

    # Group by company
    company_map = {}
    company_cache = {}
    for rec in records:
        key = get_checkin_record_company_name(rec, cache=company_cache) or "Không xác định"
        if key not in company_map:
            company_map[key] = {
                "company_name":    key,
                "exam_start":      rec.snapshot_exam_start,
                "exam_end":        rec.snapshot_exam_end,
                "total_checkin":   0,
                "total_checkout":  0,
                "total_deferred":  0,
                "records":         [],
            }
        entry = company_map[key]
        entry["records"].append(rec)
        if rec.status == CheckInStatus.CHECKED_IN:
            entry["total_checkin"] += 1
        elif rec.status == CheckInStatus.CHECKED_OUT:
            entry["total_checkout"] += 1
        elif rec.status == CheckInStatus.DEFERRED:
            entry["total_deferred"] += 1

    result = sorted(company_map.values(), key=lambda x: x["company_name"])
    total_all = len(records)
    return result, total_all, exam_date


def get_recent_checkins(exam_date: date = None, limit: int = 20):
    """Lấy danh sách check-in gần nhất trong ngày."""
    exam_date = exam_date or date.today()
    return (
        CheckInRecord.objects
        .filter(exam_date=exam_date)
        .select_related("his_patient_sync", "schedule_config", "schedule_config__his_package", "schedule_config__his_package__organization")
        .order_by("-created_at")[:limit]
    )
