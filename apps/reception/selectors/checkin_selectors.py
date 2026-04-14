"""
apps/reception/selectors/checkin_selectors.py
===============================================
Truy vấn dữ liệu check-in cho sidebar thống kê.
"""

from datetime import date

from django.db.models import Count, Q

from apps.reception.models import CheckInRecord, CheckInStatus


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
        .order_by("snapshot_company_name", "-checked_in_at")
    )

    # Group by company
    company_map = {}
    for rec in records:
        key = rec.snapshot_company_name or "Không xác định"
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
        .order_by("-created_at")[:limit]
    )
