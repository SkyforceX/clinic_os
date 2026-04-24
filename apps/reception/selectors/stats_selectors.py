"""
apps/reception/selectors/stats_selectors.py
=============================================
Truy vấn dữ liệu cho trang thống kê lượt khám.

Các nhóm dữ liệu:
1. active_company_progress  — Công ty đang/sắp có lịch khám, tiến độ check-in/out
2. daily_summary            — Thống kê theo từng ngày trong khoảng thời gian
3. period_aggregate         — Tổng hợp: hôm nay, tuần, tháng
4. peak_hours               — Phân bố check-in theo giờ trong ngày
5. company_completion_rate  — Tỷ lệ hoàn thành theo từng công ty
6. recent_activity_feed     — Feed hoạt động 30 bản ghi gần nhất
7. patient_checkin_list     — Danh sách KH của 1 công ty kèm trạng thái
"""

from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncHour, TruncWeek, TruncMonth


def get_active_company_progress(reference_date=None):
    """
    Lấy danh sách công ty đang có lịch khám (chưa kết thúc),
    gồm: tổng KH đăng ký, đã check-in, đã check-out, hoãn, chưa đến.

    Returns: list of dicts, sorted by exam_start_date asc.
    """
    from apps.reception.models import CheckInRecord, CheckInStatus
    from apps.scheduling.models import ContractScheduleConfig

    ref = reference_date or date.today()

    configs = (
        ContractScheduleConfig.objects
        .filter(exam_end_date__gte=ref)
        .select_related("quotation", "quotation__company", "his_package", "his_package__organization")
        .order_by("exam_start_date")
    )

    result = []
    for cfg in configs:
        q = cfg.quotation
        his_package = getattr(cfg, "his_package", None)
        company_name = ""
        if his_package:
            company_name = (
                his_package.company_name
                or getattr(getattr(his_package, "organization", None), "name", "")
            )
        if not company_name and q:
            company_name = getattr(q, "company_name", "") or (q.company.name if q.company else "")

        planned = (
            getattr(his_package, "total_patients", 0)
            or cfg.planned_employee_count
            or 0
        )

        # ── Query records: dùng OR(FK match | tên+khoảng ngày) ──────────
        # Bug cũ: chỉ filter schedule_config=cfg → nếu lookup_patient đã
        # link record vào một config khác của cùng công ty (do .first()
        # không có ordering), hoặc schedule_config=NULL, thì count = 0.
        #
        # Fix: kết hợp FK match VÀ snapshot_company_name + date range.
        # .distinct() tránh double-count khi record khớp cả hai điều kiện.
        if company_name:
            base_qs = CheckInRecord.objects.filter(
                Q(schedule_config=cfg)
                | Q(
                    snapshot_company_name=company_name,
                    exam_date__range=[cfg.exam_start_date, cfg.exam_end_date],
                )
            ).distinct()
        else:
            base_qs = CheckInRecord.objects.filter(schedule_config=cfg)

        ci_count  = base_qs.filter(status=CheckInStatus.CHECKED_IN).count()
        co_count  = base_qs.filter(status=CheckInStatus.CHECKED_OUT).count()
        df_count  = base_qs.filter(status=CheckInStatus.DEFERRED).count()
        total_arrived = ci_count + co_count + df_count
        not_arrived   = max(0, planned - total_arrived)

        # Ngày còn lại trong lịch khám
        remaining_days = max(0, (cfg.exam_end_date - ref).days)
        is_today = cfg.exam_start_date <= ref <= cfg.exam_end_date
        is_upcoming = cfg.exam_start_date > ref

        completion_pct = round(co_count / planned * 100) if planned > 0 else 0
        arrival_pct    = round(total_arrived / planned * 100) if planned > 0 else 0

        result.append({
            "config_id":       cfg.pk,
            "company_name":    company_name,
            "exam_start":      cfg.exam_start_date,
            "exam_end":        cfg.exam_end_date,
            "planned":         planned,
            "checked_in":      ci_count,
            "checked_out":     co_count,
            "deferred":        df_count,
            "total_arrived":   total_arrived,
            "not_arrived":     not_arrived,
            "completion_pct":  completion_pct,
            "arrival_pct":     arrival_pct,
            "remaining_days":  remaining_days,
            "is_active_today": is_today,
            "is_upcoming":     is_upcoming,
        })
    return result


def get_daily_summary(date_from, date_to):
    """
    Thống kê theo từng ngày trong khoảng [date_from, date_to].

    Returns: {
        dates: list[date],
        rows:  list[{date, checkin, checkout, deferred, total, companies}],
        totals: {checkin, checkout, deferred, total}
    }
    """
    from apps.reception.models import CheckInRecord, CheckInStatus

    records = (
        CheckInRecord.objects
        .filter(exam_date__range=[date_from, date_to])
        .values("exam_date", "status", "snapshot_company_name")
    )

    day_map = defaultdict(lambda: {
        "checkin": 0, "checkout": 0, "deferred": 0, "companies": set()
    })

    for rec in records:
        d   = rec["exam_date"]
        st  = rec["status"]
        co  = rec["snapshot_company_name"] or "?"
        day_map[d]["companies"].add(co)
        if st == CheckInStatus.CHECKED_IN:
            day_map[d]["checkin"] += 1
        elif st == CheckInStatus.CHECKED_OUT:
            day_map[d]["checkout"] += 1
        elif st == CheckInStatus.DEFERRED:
            day_map[d]["deferred"] += 1

    # Build sorted date list
    num_days = (date_to - date_from).days + 1
    dates = [date_from + timedelta(days=i) for i in range(num_days)]

    rows = []
    totals = {"checkin": 0, "checkout": 0, "deferred": 0, "total": 0, "companies": 0}

    for d in dates:
        entry = day_map.get(d, {"checkin": 0, "checkout": 0, "deferred": 0, "companies": set()})
        total = entry["checkin"] + entry["checkout"] + entry["deferred"]
        rows.append({
            "date":      d,
            "checkin":   entry["checkin"],
            "checkout":  entry["checkout"],
            "deferred":  entry["deferred"],
            "total":     total,
            "companies": len(entry["companies"]),
        })
        totals["checkin"]  += entry["checkin"]
        totals["checkout"] += entry["checkout"]
        totals["deferred"] += entry["deferred"]
        totals["total"]    += total
        totals["companies"] = max(totals["companies"], len(entry["companies"]))

    # Total unique companies across all days
    all_companies = set()
    for d in dates:
        all_companies.update(day_map.get(d, {}).get("companies", set()))
    totals["unique_companies"] = len(all_companies)

    return {"dates": dates, "rows": rows, "totals": totals}


def get_period_aggregate():
    """
    Tổng hợp cho hôm nay / tuần này / tháng này.

    Returns dict với keys: today, week, month — mỗi key là dict counts.
    """
    from apps.reception.models import CheckInRecord, CheckInStatus

    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def counts(qs):
        ci = qs.filter(status=CheckInStatus.CHECKED_IN).count()
        co = qs.filter(status=CheckInStatus.CHECKED_OUT).count()
        df = qs.filter(status=CheckInStatus.DEFERRED).count()
        total = ci + co + df
        companies = qs.values("snapshot_company_name").distinct().count()
        return {
            "checkin": ci, "checkout": co, "deferred": df,
            "total": total, "companies": companies,
        }

    base = CheckInRecord.objects
    return {
        "today": counts(base.filter(exam_date=today)),
        "week":  counts(base.filter(exam_date__gte=week_start, exam_date__lte=today)),
        "month": counts(base.filter(exam_date__gte=month_start, exam_date__lte=today)),
    }


def get_peak_hours(date_from, date_to):
    """
    Phân bố số lượt check-in theo giờ (0-23) trong khoảng thời gian.
    Returns list[{hour, count}] sorted by hour.
    """
    import pytz
    from apps.reception.models import CheckInRecord, CheckInStatus

    local_tz = pytz.timezone("Asia/Ho_Chi_Minh")

    records = CheckInRecord.objects.filter(
        exam_date__range=[date_from, date_to],
        checked_in_at__isnull=False,
    ).exclude(status=CheckInStatus.CHECKED_OUT)

    hour_map = defaultdict(int)
    for rec in records.values_list("checked_in_at", flat=True):
        if rec:
            local_time = rec.astimezone(local_tz)
            hour_map[local_time.hour] += 1

    return [{"hour": h, "count": hour_map.get(h, 0)} for h in range(7, 20)]


def get_company_completion_table(date_from, date_to):
    """
    Bảng tỷ lệ hoàn thành theo công ty trong khoảng thời gian.
    Kết hợp dữ liệu từ CheckInRecord + ContractScheduleConfig.

    Returns list[{company, planned, arrived, completed, completion_pct, avg_per_day}]
    """
    from apps.reception.models import CheckInRecord, CheckInStatus
    from apps.scheduling.models import ContractScheduleConfig

    records = (
        CheckInRecord.objects
        .filter(exam_date__range=[date_from, date_to])
        .values("snapshot_company_name", "status", "schedule_config_id")
    )

    company_stats = defaultdict(lambda: {
        "checkin": 0, "checkout": 0, "deferred": 0,
        "config_ids": set(),
    })

    for rec in records:
        name = rec["snapshot_company_name"] or "Không xác định"
        st   = rec["status"]
        company_stats[name]["config_ids"].add(rec["schedule_config_id"])
        if st == CheckInStatus.CHECKED_IN:
            company_stats[name]["checkin"] += 1
        elif st == CheckInStatus.CHECKED_OUT:
            company_stats[name]["checkout"] += 1
        elif st == CheckInStatus.DEFERRED:
            company_stats[name]["deferred"] += 1

    # Get planned counts from schedule configs
    all_config_ids = set()
    for v in company_stats.values():
        all_config_ids.update(v["config_ids"])

    planned_map = {}
    if all_config_ids:
        for cfg in ContractScheduleConfig.objects.filter(pk__in=all_config_ids):
            q = cfg.quotation
            name = getattr(q, "company_name", "") if q else ""
            if not name and q and q.company:
                name = q.company.name
            if name:
                planned_map[name] = planned_map.get(name, 0) + (cfg.planned_employee_count or 0)

    num_days = max(1, (date_to - date_from).days + 1)
    result = []
    for name, data in company_stats.items():
        arrived   = data["checkin"] + data["checkout"] + data["deferred"]
        completed = data["checkout"]
        planned   = planned_map.get(name, 0)
        arrival_pct    = round(arrived / planned * 100)   if planned > 0 else 0
        completion_pct = round(completed / arrived * 100) if arrived  > 0 else 0
        result.append({
            "company":         name,
            "planned":         planned,
            "arrived":         arrived,
            "checked_in":      data["checkin"],
            "checked_out":     completed,
            "deferred":        data["deferred"],
            "not_arrived":     max(0, planned - arrived),
            "arrival_pct":     arrival_pct,
            "completion_pct":  completion_pct,
            "avg_per_day":     round(arrived / num_days, 1),
        })

    return sorted(result, key=lambda x: x["arrived"], reverse=True)


def get_admin_insights(date_from, date_to):
    """
    Insights quản trị:
    - Ngày bận nhất
    - Công ty đến nhiều nhất
    - Tỷ lệ checkout trung bình
    - Số KH hoãn cao nhất trong 1 ngày
    - Trung bình KH/ngày làm việc
    """
    from apps.reception.models import CheckInRecord, CheckInStatus

    records = list(
        CheckInRecord.objects
        .filter(exam_date__range=[date_from, date_to])
        .values("exam_date", "status", "snapshot_company_name", "checked_in_at")
    )

    if not records:
        return {}

    day_totals   = defaultdict(int)
    company_cnt  = defaultdict(int)
    total_ci     = 0
    total_co     = 0
    total_df     = 0

    for rec in records:
        day_totals[rec["exam_date"]] += 1
        company_cnt[rec["snapshot_company_name"] or "?"] += 1
        if rec["status"] == CheckInStatus.CHECKED_IN:
            total_ci += 1
        elif rec["status"] == CheckInStatus.CHECKED_OUT:
            total_co += 1
        elif rec["status"] == CheckInStatus.DEFERRED:
            total_df += 1

    total_all = total_ci + total_co + total_df
    active_days = len(day_totals)

    busiest_day   = max(day_totals.items(), key=lambda x: x[1]) if day_totals   else (None, 0)
    top_company   = max(company_cnt.items(), key=lambda x: x[1]) if company_cnt else (None, 0)

    return {
        "total":            total_all,
        "total_checkin":    total_ci,
        "total_checkout":   total_co,
        "total_deferred":   total_df,
        "active_days":      active_days,
        "avg_per_day":      round(total_all / active_days, 1) if active_days else 0,
        "checkout_rate":    round(total_co / total_all * 100) if total_all   else 0,
        "deferred_rate":    round(total_df / total_all * 100) if total_all   else 0,
        "busiest_day":      busiest_day[0],
        "busiest_day_count":busiest_day[1],
        "top_company":      top_company[0],
        "top_company_count":top_company[1],
    }


def get_chart_data(rows):
    """
    Chuyển daily summary rows → JSON-serializable dict cho Chart.js.
    """
    labels   = [r["date"].strftime("%d/%m") for r in rows]
    checkin  = [r["checkin"]  for r in rows]
    checkout = [r["checkout"] for r in rows]
    deferred = [r["deferred"] for r in rows]
    total    = [r["total"]    for r in rows]
    return {
        "labels":   labels,
        "checkin":  checkin,
        "checkout": checkout,
        "deferred": deferred,
        "total":    total,
    }


def get_patient_checkin_list(company_name, date_from, date_to):
    """
    Danh sách bệnh nhân của một công ty trong kỳ lọc, kèm trạng thái.

    Dùng để hiển thị trong modal "DS khách hàng" ở bảng thống kê theo công ty.

    Nguồn dữ liệu:
    1. CheckInRecord (snapshot)       → bệnh nhân đã đến (CHECKED_IN / CHECKED_OUT / DEFERRED)
    2. HisExamRecordSync + scheduling → bệnh nhân đăng ký nhưng chưa đến (NOT_ARRIVED)

    Returns list[dict] sorted: Chưa đến → Quay lại sau → Đang khám → Hoàn thành
    """
    from apps.reception.models import CheckInRecord, CheckInStatus

    STATUS_META = {
        CheckInStatus.CHECKED_IN:  ("Đang khám",     "ci"),
        CheckInStatus.CHECKED_OUT: ("Đã hoàn thành", "co"),
        CheckInStatus.DEFERRED:    ("Quay lại sau",   "df"),
    }

    # ── 1. Bệnh nhân đã check-in (từ snapshot) ──────────────────────
    checkin_qs = (
        CheckInRecord.objects
        .filter(
            snapshot_company_name=company_name,
            exam_date__range=[date_from, date_to],
        )
        .order_by("snapshot_ma_bn", "-checked_in_at")
    )

    seen_mabn = set()
    result    = []

    for rec in checkin_qs:
        if rec.snapshot_ma_bn in seen_mabn:
            continue  # giữ bản ghi mới nhất của mỗi mã BN
        seen_mabn.add(rec.snapshot_ma_bn)

        lbl, cls = STATUS_META.get(rec.status, (rec.status, ""))
        result.append({
            "ma_bn":          rec.snapshot_ma_bn,
            "ho_ten":         rec.snapshot_ho_ten,
            "ngay_sinh":      rec.snapshot_ngay_sinh.strftime("%d/%m/%Y") if rec.snapshot_ngay_sinh else "—",
            "gioi_tinh":      rec.gioi_tinh_display,
            "status":         rec.status,
            "status_display": lbl,
            "status_class":   cls,
            "exam_date":      rec.exam_date.strftime("%d/%m/%Y"),
        })

    # ── 2. Bệnh nhân chưa check-in (từ HIS exam records) ────────────
    # Tìm bệnh nhân thuộc gói HIS có schedule config đang trong kỳ
    try:
        from apps.his_integration.models import HisExamRecordSync
        from apps.scheduling.models import ContractScheduleConfig

        configs = (
            ContractScheduleConfig.objects
            .filter(
                exam_start_date__lte=date_to,
                exam_end_date__gte=date_from,
            )
            .filter(
                Q(his_package__company_name=company_name)
                | Q(his_package__organization__name=company_name)
                | Q(quotation__company__name=company_name)
                | Q(quotation__company_name=company_name)
            )
            .values_list("his_package_id", flat=True)
        )
        package_ids = [package_id for package_id in configs if package_id]

        if package_ids:
            not_arrived_qs = (
                HisExamRecordSync.objects
                .filter(
                    package_sync_id__in=package_ids,
                    is_active=True,
                    patient_sync__is_active=True,
                )
                .exclude(patient_sync__his_patient_code__in=seen_mabn)
                .select_related("patient_sync")
                .order_by("patient_sync__his_patient_code")
            )
            for record in not_arrived_qs:
                p = record.patient_sync
                if p.his_patient_code in seen_mabn:
                    continue
                result.append({
                    "ma_bn":          p.ma_bn,
                    "ho_ten":         p.ho_ten,
                    "ngay_sinh":      p.ngay_sinh.strftime("%d/%m/%Y") if p.ngay_sinh else "—",
                    "gioi_tinh":      p.gioi_tinh or "—",
                    "status":         "NOT_ARRIVED",
                    "status_display": "Chưa đến",
                    "status_class":   "na",
                    "exam_date":      "—",
                })
                seen_mabn.add(p.ma_bn)
    except Exception:
        pass  # graceful fallback nếu model chưa available

    # ── 3. Sắp xếp: Chưa đến → Hoãn → Đang khám → Hoàn thành ───────
    ORDER = {
        "NOT_ARRIVED": 0,
        CheckInStatus.DEFERRED:    1,
        CheckInStatus.CHECKED_IN:  2,
        CheckInStatus.CHECKED_OUT: 3,
    }
    result.sort(key=lambda x: (ORDER.get(x["status"], 9), x.get("ho_ten", "")))

    return result
