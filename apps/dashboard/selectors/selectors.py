"""
dashboard/selectors/selectors.py
==================================
Tất cả truy vấn dữ liệu cho trang tổng quan.
Không import vòng lặp, không gọi render/redirect.

Cập nhật: thay get_doctor_schedules_for_week (DoctorSchedule tuần)
           bằng get_work_schedule_today + get_work_schedule_for_week
           sử dụng WorkSchedule (toàn phòng khám theo ngày).
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
    Trả về các kế hoạch triển khai đang thực hiện hoặc sắp tới (45 ngày tới).
    """
    from apps.contract.models.contract import Contract, ContractStatus

    today = today or date.today()
    cutoff = today + timedelta(days=45)

    plans_qs = (
        Contract.objects
        .filter(status__in=[ContractStatus.APPROVED, ContractStatus.ACTIVE])
        .filter(Q(end_date__gte=today) | Q(end_date__isnull=True))
        .filter(Q(start_date__lte=cutoff) | Q(start_date__isnull=True))
        .filter(implementation_plan__isnull=False)
        .select_related("company", "corporate_profile", "implementation_plan")
        .order_by("start_date", "id")
    )

    result = []
    for contract in plans_qs:
        profile = getattr(contract, "corporate_profile", None)
        plan    = getattr(contract, "implementation_plan", None)
        if not plan:
            continue
        rows = plan.rows_json or []
        total_rows  = len(rows)
        locked_rows = sum(1 for r in rows if r.get("is_locked"))
        result.append({
            "contract_id":     contract.pk,
            "contract_number": contract.contract_number or f"#{contract.pk}",
            "company_name":    (profile.company_name_snapshot if profile else None) or contract.company.name,
            "status":          contract.status,
            "status_display":  contract.get_status_display(),
            "start_date":      contract.start_date,
            "end_date":        contract.end_date,
            "total_rows":      total_rows,
            "locked_rows":     locked_rows,
            "progress_pct":    int(locked_rows * 100 / total_rows) if total_rows else 0,
            "is_ongoing":      (contract.start_date or date.min) <= today,
        })
    return result


# ── Phần chung: Lịch khám doanh nghiệp theo tuần ─────────────────────────────

def get_corporate_bookings_by_week(week_start, week_end):
    """
    Trả về dữ liệu lịch khám theo ngày trong tuần và tổng tuần đã khử trùng lặp.

    - `days`: list 7 item (Mon→Sun):
      { date, day_label, is_today, companies: [{name, pax, contract_id, config_id}], total_pax }
    - `summary`:
      {
        "schedule_count": số lịch khám duy nhất có ngày thuộc tuần,
        "company_count": số công ty duy nhất có lịch trong tuần,
        "planned_pax": tổng planned_employee_count, mỗi lịch chỉ tính 1 lần,
      }
    """
    from apps.scheduling.models.schedule import ContractScheduleConfig

    overlapping = (
        ContractScheduleConfig.objects
        .filter(exam_start_date__lte=week_end, exam_end_date__gte=week_start)
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
    weekly_schedule_map = {}
    weekly_company_keys = set()

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
                company_key = (
                    getattr(cfg, "id", None),
                    contract.pk if contract else None,
                    company_name,
                )
                weekly_schedule_map[company_key] = {
                    "config_id": getattr(cfg, "id", None),
                    "contract_id": contract.pk if contract else None,
                    "company_name": company_name,
                    "planned_pax": cfg.planned_employee_count or 0,
                }
                weekly_company_keys.add((contract.pk if contract else None, company_name))
                companies.append({
                    "name":        company_name,
                    "pax":         cfg.planned_employee_count,
                    "contract_id": contract.pk if contract else None,
                    "config_id":   getattr(cfg, "id", None),
                })

        result.append({
            "date":      day,
            "day_label": vn_day_labels[offset],
            "is_today":  day == today,
            "companies": companies,
            "total_pax": sum(c["pax"] for c in companies),
        })

    return {
        "days": result,
        "summary": {
            "schedule_count": len(weekly_schedule_map),
            "company_count": len(weekly_company_keys),
            "planned_pax": sum(item["planned_pax"] for item in weekly_schedule_map.values()),
        },
    }


# ── Phần chung: Lịch làm việc toàn phòng khám hôm nay ───────────────────────

def get_work_schedule_today(target_date=None):
    """
    Trả về lịch làm việc hôm nay (hoặc target_date), grouped by department.
    Format:
    [
      {
        "dept_name": "Nội Khoa",
        "dept_order": 1,
        "employees": [
          {"name": str, "position": str, "shift": "F"|"S"|"C"|"L"|"O"|"",
           "shift_label": str, "shift_css": str, "emp_id": int},
          ...
        ],
        "working_count": int,  # F + S + C
      },
      ...
    ]
    """
    from apps.hrm.models.work_schedule import WorkSchedule, SHIFT_DISPLAY
    from apps.hrm.models.employee import Employee, EmployeeStatus

    target_date = target_date or date.today()

    # Load tất cả schedules hôm nay
    schedules = (
        WorkSchedule.objects
        .filter(schedule_date=target_date)
        .select_related("employee", "employee__department", "employee__position")
    )
    schedule_map = {ws.employee_id: ws.shift for ws in schedules}

    # Load active employees
    employees = (
        Employee.objects
        .filter(status__in=[EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION])
        .select_related("department", "position")
        .order_by("department__display_order", "department__name", "full_name")
    )

    dept_map = {}
    for emp in employees:
        dept    = emp.department
        dk      = dept.pk if dept else 0
        dname   = dept.name if dept else "Chưa phân phòng"
        dorder  = dept.display_order if dept else 999

        if dk not in dept_map:
            dept_map[dk] = {
                "dept_name":     dname,
                "dept_order":    dorder,
                "employees":     [],
                "working_count": 0,
            }

        shift = schedule_map.get(emp.pk, "")
        disp  = SHIFT_DISPLAY.get(shift, {"label": "", "title": "Chưa đăng ký", "css": "shift-empty"})

        dept_map[dk]["employees"].append({
            "emp_id":      emp.pk,
            "name":        emp.full_name,
            "position":    emp.position.name if emp.position else "",
            "shift":       shift,
            "shift_label": disp["title"],
            "shift_css":   disp["css"],
        })
        if shift in ("F", "S", "C"):
            dept_map[dk]["working_count"] += 1

    result = sorted(dept_map.values(), key=lambda x: (x["dept_order"], x["dept_name"]))
    return result, target_date


def get_work_schedule_week_summary(week_start, week_end):
    """
    Trả về dict: date → {shift_counts: {F,S,C,L,O,empty}, total_working}
    Dùng để vẽ mini heatmap tuần trong dashboard.
    """
    from apps.hrm.models.work_schedule import WorkSchedule

    schedules = WorkSchedule.objects.filter(
        schedule_date__gte=week_start,
        schedule_date__lte=week_end,
    ).values("schedule_date", "shift")

    summary = {}
    for ws in schedules:
        d = ws["schedule_date"]
        s = ws["shift"] or ""
        if d not in summary:
            summary[d] = {"F": 0, "S": 0, "C": 0, "L": 0, "O": 0, "": 0, "working": 0}
        summary[d][s] = summary[d].get(s, 0) + 1
        if s in ("F", "S", "C"):
            summary[d]["working"] += 1

    return summary


# ── BACKWARD COMPAT: giữ hàm cũ cho DoctorSchedule nếu cần ──────────────────

def get_doctor_schedules_for_week(week_start):
    """
    [GIỮ NGUYÊN] Lịch bác sĩ (DoctorSchedule per week).
    Dùng trong doctor_schedule_list view. Dashboard đã chuyển sang WorkSchedule.
    """
    try:
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
                    "shift":      shift,
                    "label":      SHIFT_LABELS.get(shift, "") if shift else "",
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
    except Exception:
        return []


# ── Phần riêng: Executive / Manager ──────────────────────────────────────────

def get_executive_stats(user):
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
        "draft":     Contract.objects.filter(status=ContractStatus.DRAFT).count(),
        "submitted": Contract.objects.filter(status=ContractStatus.SUBMITTED).count(),
        "approved":  Contract.objects.filter(status=ContractStatus.APPROVED).count(),
        "active":    Contract.objects.filter(status=ContractStatus.ACTIVE).count(),
        "finished":  Contract.objects.filter(status=ContractStatus.FINISHED).count(),
        "total":     Contract.objects.count(),
    }
    task_stage_counts = []
    for stage in TaskStage.values:
        cnt = Task.objects.filter(created_by=user, stage=stage).count()
        task_stage_counts.append({
            "stage": stage,
            "label": TaskStage(stage).label,
            "count": cnt,
        })

    pending_approvals = ApprovalRequest.objects.filter(status=ApprovalStatus.PENDING).count()
    return {
        "quotation_counts":    quotation_counts,
        "contract_counts":     contract_counts,
        "task_stage_counts":   task_stage_counts,
        "tasks_created_total": Task.objects.filter(created_by=user).count(),
        "pending_approvals":   pending_approvals,
    }


def get_sales_stats(user):
    """Sales Team: chỉ đếm quotation/contract do user này tạo."""
    from apps.contract.models.quotation import QuotationDraft, QuotationStatus
    from apps.contract.models.contract import Contract, ContractStatus
    from apps.tasks.models.task import Task, TaskStage
    from apps.approvals.models.approval_request import ApprovalRequest, ApprovalStatus

    quotation_counts = {
        "draft":     QuotationDraft.objects.filter(created_by=user, status=QuotationStatus.DRAFT).count(),
        "submitted": QuotationDraft.objects.filter(created_by=user, status=QuotationStatus.SUBMITTED).count(),
        "approved":  QuotationDraft.objects.filter(created_by=user, status=QuotationStatus.APPROVED).count(),
        "total":     QuotationDraft.objects.filter(created_by=user).count(),
    }
    contract_counts = {
        "draft":     Contract.objects.filter(created_by=user, status=ContractStatus.DRAFT).count(),
        "submitted": Contract.objects.filter(created_by=user, status=ContractStatus.SUBMITTED).count(),
        "approved":  Contract.objects.filter(created_by=user, status=ContractStatus.APPROVED).count(),
        "active":    Contract.objects.filter(created_by=user, status=ContractStatus.ACTIVE).count(),
        "finished":  Contract.objects.filter(created_by=user, status=ContractStatus.FINISHED).count(),
        "total":     Contract.objects.filter(created_by=user).count(),
    }
    task_stage_counts = []
    for stage in TaskStage.values:
        cnt = Task.objects.filter(assignee=user, stage=stage).count()
        task_stage_counts.append({"stage": stage, "label": TaskStage(stage).label, "count": cnt})

    my_approvals = {
        "pending":  ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.PENDING).count(),
        "approved": ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.APPROVED).count(),
        "rejected": ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.REJECTED).count(),
        "total":    ApprovalRequest.objects.filter(requested_by=user).count(),
    }
    return {
        "quotation_counts":    quotation_counts,
        "contract_counts":     contract_counts,
        "task_stage_counts":   task_stage_counts,
        "tasks_assigned_total": Task.objects.filter(assignee=user).count(),
        "my_approvals":        my_approvals,
    }


def get_staff_stats(user):
    from apps.tasks.models.task import Task, TaskStage
    from apps.approvals.models.approval_request import ApprovalRequest, ApprovalStatus

    task_stage_counts = []
    for stage in TaskStage.values:
        cnt = Task.objects.filter(assignee=user, stage=stage).count()
        task_stage_counts.append({"stage": stage, "label": TaskStage(stage).label, "count": cnt})

    my_approvals = {
        "pending":  ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.PENDING).count(),
        "approved": ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.APPROVED).count(),
        "rejected": ApprovalRequest.objects.filter(requested_by=user, status=ApprovalStatus.REJECTED).count(),
        "total":    ApprovalRequest.objects.filter(requested_by=user).count(),
    }
    return {
        "task_stage_counts":    task_stage_counts,
        "tasks_assigned_total": Task.objects.filter(assignee=user).count(),
        "my_approvals":         my_approvals,
    }


# ── My work schedule (cho nhân viên đang đăng nhập) ─────────────────────────

def get_my_schedule_this_week(user, week_start, week_end):
    """
    Trả về lịch của nhân viên đang đăng nhập trong tuần hiện tại.
    { date: shift_or_empty }
    """
    from apps.hrm.models.work_schedule import WorkSchedule, SHIFT_DISPLAY

    emp = getattr(user, "employee_profile", None)
    if not emp:
        return None, []

    schedules = WorkSchedule.objects.filter(
        employee=emp,
        schedule_date__gte=week_start,
        schedule_date__lte=week_end,
    )
    sched_map = {ws.schedule_date: ws.shift for ws in schedules}

    days = []
    vn_labels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    today = date.today()
    for i in range(7):
        d = week_start + timedelta(days=i)
        shift = sched_map.get(d, "")
        disp = SHIFT_DISPLAY.get(shift, {"label": "·", "title": "Chưa đăng ký", "css": "shift-empty"})
        days.append({
            "date":     d,
            "weekday":  vn_labels[i],
            "shift":    shift,
            "label":    disp["label"],
            "title":    disp["title"],
            "css":      disp["css"],
            "is_today": d == today,
        })
    return emp, days
