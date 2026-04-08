"""
apps.hrm.services.onboard
─────────────────────────
Tiếp nhận nhân viên mới vào hệ thống.

Luồng:
  1. Validate dữ liệu đầu vào
  2. Tạo Employee record
  3. (Tùy chọn) Tạo Django User và liên kết
  4. Cấp Django Group theo chức vụ (PositionGroupMapping)
  5. Ghi AccessLog(ONBOARD)
  6. Đẩy notification cho HR Admin

Gọi từ view:
    from apps.hrm.services.onboard import execute as onboard_employee
    employee = onboard_employee(payload=payload, actor=request.user)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.hrm.exceptions import HRMPermissionDenied, HRMValidationError
from apps.hrm.models.access_control import AccessLog, AccessLogAction
from apps.hrm.models.employee import Employee, EmployeeStatus, EmploymentType
from apps.hrm.policies import HRMPolicy
from apps.hrm.services.grant_access import grant_access_by_position

User = get_user_model()


@dataclass
class OnboardPayload:
    """Dữ liệu đầu vào cho quá trình onboard."""

    employee_code:   str
    full_name:       str
    department_id:   Optional[int]
    position_id:     Optional[int]
    employment_type: str = EmploymentType.FULLTIME
    hire_date:       Optional[date] = None
    probation_end_date: Optional[date] = None

    # Thông tin cá nhân (tùy chọn)
    gender:           str = ""
    date_of_birth:    Optional[date] = None
    phone:            str = ""
    email:            str = ""
    address:          str = ""
    id_card_number:   str = ""
    tax_code:         str = ""
    social_insurance_code: str = ""
    bank_account:     str = ""
    bank_name:        str = ""
    direct_manager_id: Optional[int] = None
    note:             str = ""

    # Tùy chọn tạo tài khoản hệ thống ngay
    create_user:    bool = False
    username:       str = ""
    password:       str = ""


@transaction.atomic
def execute(*, payload: OnboardPayload, actor) -> Employee:
    """
    Tạo hồ sơ nhân viên mới và cấp quyền theo chức vụ.

    actor phải thuộc nhóm HR Admin.
    Raises HRMPermissionDenied, HRMValidationError.
    """
    if not HRMPolicy.can_onboard(actor):
        raise HRMPermissionDenied("Bạn không có quyền tiếp nhận nhân viên mới.")

    # ── Validate ──────────────────────────────────────────────────────────────
    if not payload.employee_code.strip():
        raise HRMValidationError("Mã nhân viên không được để trống.")
    if not payload.full_name.strip():
        raise HRMValidationError("Họ và tên không được để trống.")
    if Employee.objects.filter(employee_code=payload.employee_code).exists():
        raise HRMValidationError(f"Mã nhân viên '{payload.employee_code}' đã tồn tại.")

    if payload.create_user:
        if not payload.username.strip():
            raise HRMValidationError("Username không được để trống khi tạo tài khoản.")
        if User.objects.filter(username=payload.username).exists():
            raise HRMValidationError(f"Username '{payload.username}' đã tồn tại.")

    # ── Resolve FKs ───────────────────────────────────────────────────────────
    from apps.hrm.models.department import Department, Position

    department = None
    if payload.department_id:
        department = Department.objects.filter(pk=payload.department_id).first()
        if not department:
            raise HRMValidationError("Phòng ban không tồn tại.")

    position = None
    if payload.position_id:
        position = Position.objects.filter(pk=payload.position_id).first()
        if not position:
            raise HRMValidationError("Chức vụ không tồn tại.")

    direct_manager = None
    if payload.direct_manager_id:
        direct_manager = Employee.objects.filter(pk=payload.direct_manager_id).first()

    # ── Tạo Django User (nếu yêu cầu) ────────────────────────────────────────
    user = None
    if payload.create_user:
        user = User.objects.create_user(
            username=payload.username,
            password=payload.password or User.objects.make_random_password(),
            email=payload.email,
            first_name=payload.full_name.split()[-1] if payload.full_name else "",
            last_name=" ".join(payload.full_name.split()[:-1]) if payload.full_name else "",
        )

    # ── Tạo Employee ──────────────────────────────────────────────────────────
    initial_status = (
        EmployeeStatus.PROBATION
        if payload.employment_type == EmploymentType.PROBATION
        else EmployeeStatus.PROBATION  # Mặc định bắt đầu thử việc
    )

    employee = Employee.objects.create(
        user=user,
        employee_code=payload.employee_code.strip(),
        full_name=payload.full_name.strip(),
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        id_card_number=payload.id_card_number,
        tax_code=payload.tax_code,
        social_insurance_code=payload.social_insurance_code,
        bank_account=payload.bank_account,
        bank_name=payload.bank_name,
        department=department,
        position=position,
        direct_manager=direct_manager,
        employment_type=payload.employment_type,
        hire_date=payload.hire_date,
        probation_end_date=payload.probation_end_date,
        status=initial_status,
        note=payload.note,
        created_by=actor,
    )

    # ── Cấp quyền theo chức vụ ───────────────────────────────────────────────
    granted_groups = grant_access_by_position(employee=employee, actor=actor)

    # ── Ghi ONBOARD log ───────────────────────────────────────────────────────
    AccessLog.objects.create(
        employee=employee,
        action=AccessLogAction.ONBOARD,
        actor=actor,
        note=(
            f"Onboard bởi {actor.get_full_name() or actor.username}. "
            f"Chức vụ: {position}. "
            f"Nhóm được cấp: {', '.join(granted_groups) or '(chưa có mapping)'}"
        ),
    )

    # ── Notification (fire-and-forget) ────────────────────────────────────────
    _notify_onboard(employee=employee, actor=actor)

    return employee


def _notify_onboard(*, employee: Employee, actor) -> None:
    """Gửi thông báo nội bộ khi có nhân viên mới. Không raise exception."""
    try:
        from apps.notifications.models import EventType, NotificationLevel
        from apps.notifications.services.push import push

        push(
            recipients=actor,
            event_type=EventType.REMINDER,
            level=NotificationLevel.SUCCESS,
            title="Onboard thành công",
            body=f"Nhân viên {employee.full_name} ({employee.employee_code}) đã được tiếp nhận.",
            url=f"/hr/employees/{employee.pk}/",
        )
    except Exception:
        pass
