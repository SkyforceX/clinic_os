"""
dashboard/selectors.py
=======================
Tất cả truy vấn dữ liệu cho trang tổng quan.
Không import vòng lặp, không gọi render/redirect.
"""

from datetime import date, timedelta

from django.db.models import Count, Q


# ── Helpers tuần ─────────────────────────────────────────────────────────────

def get_week_bounds(ref_date=None):
    """Trả về (week_start: Monday, week_end: Sunday) của tuần chứa ref_date."""
    ref_date = ref_date or date.today()
    week_start = ref_date - timedelta(days=ref_date.weekday())
    week_end   = week_start + timedelta(days=6)
    return week_start, week_end


def get_week_days(week_start):
    """Trả về list 7 date từ thứ Hai đến CN."""
    return [week_start + timedelta(days=i) for i in range(7)]


# ── Phần chung: Kế hoạch triển khai ─────────────────────────────────────────

def get_active_implementation_plans(today=None):
    """
    Trả về các kế hoạch triển khai đang thực hiện hoặc sắp tới (30 ngày tới).
    Điều kiện:
      - Contract.status in (APPROVED, ACTIVE)
      - Contract.end_date >= today hoặc null
      - Có implementation_plan
    """
    from apps.contract.models.contract import Contract, ContractStatus

    today = today or date.today()
    cutoff = today + timedelta(days=45)

    plans_qs = (
        Contract.objects
        .filter(
            status__in=[ContractStatus.APPROVED, ContractStatus.ACTIVE],
        )
        .filter(
            Q(end_date__gte=today) | Q(end_date__isnull=True)
        )
        .filter(
            Q(start_date__lte=cutoff) | Q(start_date__isnull=True)
        )
        .filter(implementation_plan__isnull=False)
        .select_related(
            "company",
            "corporate_profile",
            "implementation_plan",
        )
        .order_by("start_date", "id")
    )

    result = []
    for contract in plans_qs:
        profile = getattr(contract, "corporate_profile", None)
        plan    = getattr(contract, "implementation_plan", None)
        if not plan:
            continue
        rows = plan.rows_json or []
        total_rows   = len(rows)
        locked_rows  = sum(1 for r in rows if r.get("is_locked"))
        result.append({
            "contract_id":      contract.pk,
            "contract_number":  contract.contract_number or f"#{contract.pk}",
            "company_name":     (profile.company_name_snapshot if profile else None) or contract.company.name,
            "status":           contract.status,
            "status_display":   contract.get_status_display(),
            "start_date":       contract.start_date,
            "end_date":         contract.end_date,
            "total_rows":       total_rows,
            "locked_rows":      locked_rows,
            "progress_pct":     int(locked_rows * 100 / total_rows) if total_rows else 0,
            "is_ongoing":       (contract.start_date or date.min) <= today,
        })

    return result


# ── Phần chung: Lịch khám doanh nghiệp theo tuần ─────────────────────────────

def get_corporate_bookings_by_week(week_start, week_end):
    """
    Trả về list 7 item (Mon→Sun), mỗi item là:
    {
        "date": date,
        "day_label": "Thứ 2",
        "is_today": bool,
        "companies": [{"name": str, "pax": int, "contract_id": int}, ...],
        "total_pax": int,
    }
    """
    from apps.scheduling.models.schedule import ContractScheduleConfig

    overlapping = (
        ContractScheduleConfig.objects
        .filter(
            exam_start_date__lte=week_end,
            exam_end_date__gte=week_start,
        )
        .select_related(
            "quotation__company",
            "contract__contract",
            "contract__contract__company",
        )
        .order_by("exam_start_date")
    )

    today = date.today()
    vn_day_labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
    result = []

    for offset in range(7):
        day = week_start + timedelta(days=offset)
        companies = []
        for cfg in overlapping:
            if cfg.exam_start_date <= day <= cfg.exam_end_date:
                profile  = cfg.contract
                contract = getattr(profile, "contract", None) if profile else None
                if cfg.quotation and cfg.quotation.company:
                    company_name = cfg.quotation.company.name
                elif profile and profile.company_name_snapshot:
                    company_name = profile.company_name_snapshot
                else:
                    company_name = "Công ty chưa xác định"
                companies.append({
                    "name":        company_name,
                    "pax":         cfg.planned_employee_count,
                    "contract_id": contract.pk if contract else None,
                })

        result.append({
            "date":       day,
            "day_label":  vn_day_labels[offset],
            "is_today":   day == today,
            "companies":  companies,
            "total_pax":  sum(c["pax"] for c in companies),
        })

    return result


# ── Phần chung: Lịch bác sĩ trong tuần ──────────────────────────────────────

def get_doctor_schedules_for_week(week_start):
    """
    Trả về list schedule theo bác sĩ cho tuần week_start.
    Mỗi item: {"doctor_name", "position", "department", "schedule_json", "schedule_display"}
    """
    from apps.hrm.models.doctor_schedule import DoctorSchedule, DAY_KEYS, SHIFT_LABELS

    schedules = (
        DoctorSchedule.objects
        .filter(week_start=week_start)
        .select_related("doctor", "doctor__position", "doctor__department")
        .order_by("doctor__full_name")
    )

    result = []
    for sched in schedules:
        sched_json = sched.schedule_json or {}
        shifts = {}
        for day in DAY_KEYS:
            shift = sched_json.get(day)
            shifts[day] = {
                "shift": shift,
                "label": SHIFT_LABELS.get(shift, "") if shift else "",
                "is_working": bool(shift),
            }
        result.append({
            "doctor_id":   sched.doctor.pk,
            "doctor_name": sched.doctor.full_name,
            "position":    sched.doctor.position.name if sched.doctor.position else "",
            "department":  sched.doctor.department.name if sched.doctor.department else "",
            "note":        sched.note,
            "shifts":      shifts,
        })

    return result


# ── Phần riêng: Executive / Manager ──────────────────────────────────────────

def get_executive_stats(user):
    """
    Stats cho Executive/Manager:
    - Báo giá theo trạng thái
    - Hợp đồng theo trạng thái
    - Tasks giao bởi user (theo stage)
    - Pending approvals đang chờ
    """
    from apps.contract.models.quotation import QuotationDraft, QuotationStatus
    from apps.contract.models.contract import Contract, ContractStatus
    from apps.tasks.models.task import Task, TaskStage
    from apps.approvals.models.approval_request import ApprovalRequest, ApprovalStatus

    quotation_counts = {
        "draft":     QuotationDraft.objects.filter(status=QuotationStatus.DRAFT).count(),
        "submitted": QuotationDraft.objects.filter(status=QuotationStatus.SUBMITTED).count(),
        "approved":  QuotationDraft.objects.filter(status=QuotationStatus.APPROVED).count(),
        "total":     QuotationDraft.objects.count(),
    }

    contract_counts = {
        "draft":      Contract.objects.filter(status=ContractStatus.DRAFT).count(),
        "submitted":  Contract.objects.filter(status=ContractStatus.SUBMITTED).count(),
        "approved":   Contract.objects.filter(status=ContractStatus.APPROVED).count(),
        "active":     Contract.objects.filter(status=ContractStatus.ACTIVE).count(),
        "finished":   Contract.objects.filter(status=ContractStatus.FINISHED).count(),
        "total":      Contract.objects.count(),
    }

    task_stage_counts = []
    for stage in TaskStage.values:
        cnt = Task.objects.filter(created_by=user, stage=stage).count()
        task_stage_counts.append({
            "stage":   stage,
            "label":   TaskStage(stage).label,
            "count":   cnt,
        })
    tasks_created_total = Task.objects.filter(created_by=user).count()

    pending_approvals = ApprovalRequest.objects.filter(status=ApprovalStatus.PENDING).count()

    return {
        "quotation_counts":   quotation_counts,
        "contract_counts":    contract_counts,
        "task_stage_counts":  task_stage_counts,
        "tasks_created_total": tasks_created_total,
        "pending_approvals":  pending_approvals,
    }


# ── Phần riêng: Staff thông thường ───────────────────────────────────────────

def get_staff_stats(user):
    """
    Stats cho nhân viên thông thường:
    - Tasks được giao (theo stage)
    - Approval requests của user này (đã gửi, đã duyệt, từ chối)
    """
    from apps.tasks.models.task import Task, TaskStage
    from apps.approvals.models.approval_request import ApprovalRequest, ApprovalStatus

    task_stage_counts = []
    for stage in TaskStage.values:
        cnt = Task.objects.filter(assignee=user, stage=stage).count()
        task_stage_counts.append({
            "stage":  stage,
            "label":  TaskStage(stage).label,
            "count":  cnt,
        })
    tasks_assigned_total = Task.objects.filter(assignee=user).count()

    my_approvals = {
        "pending":  ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.PENDING).count(),
        "approved": ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.APPROVED).count(),
        "rejected": ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.REJECTED).count(),
        "total":    ApprovalRequest.objects.filter(requested_by=user).count(),
    }

    return {
        "task_stage_counts":    task_stage_counts,
        "tasks_assigned_total": tasks_assigned_total,
        "my_approvals":         my_approvals,
    }
