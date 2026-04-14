"""
apps.hrm.services.offboard
──────────────────────────
Nghỉ việc / chấm dứt hợp đồng nhân viên.

Luồng:
  1. Kiểm tra quyền
  2. Validate: không offboard nhân viên đã nghỉ
  3. Thu hồi toàn bộ Django Group
  4. Lock Django User (is_active = False)
  5. Cập nhật Employee.status + resignation_date
  6. Ghi AccessLog(OFFBOARD)
"""

from __future__ import annotations

from datetime import date

from django.db import transaction

from apps.hrm.exceptions import HRMPermissionDenied, HRMValidationError
from apps.hrm.models.access_control import AccessLog, AccessLogAction
from apps.hrm.models.employee import Employee, EmployeeStatus
from apps.hrm.policies import HRMPolicy
from apps.hrm.services.grant_access import revoke_access_by_position


@transaction.atomic
def execute(
    *,
    employee: Employee,
    actor,
    resignation_date: date | None = None,
    reason: str = "",
    terminate: bool = False,
) -> Employee:
    """
    Xử lý nghỉ việc.

    terminate=True  → status = TERMINATED (bị chấm dứt hợp đồng)
    terminate=False → status = RESIGNED   (tự nghỉ)
    """
    if not HRMPolicy.can_offboard(actor):
        raise HRMPermissionDenied("Bạn không có quyền thực hiện thao tác nghỉ việc.")

    if employee.status in (EmployeeStatus.RESIGNED, EmployeeStatus.TERMINATED):
        raise HRMValidationError(
            f"Nhân viên {employee.full_name} đã ở trạng thái "
            f"'{employee.get_status_display()}', không thể thực hiện lại."
        )

    # ── Thu hồi tất cả Group (toàn bộ, không chỉ theo position) ─────────────
    revoked_groups: list[str] = []
    if employee.user:
        all_groups = list(employee.user.groups.all())
        for grp in all_groups:
            employee.user.groups.remove(grp)
            AccessLog.objects.create(
                employee=employee,
                action=AccessLogAction.REVOKED,
                django_group=grp,
                actor=actor,
                note=f"Thu hồi khi offboard: {reason or 'Nghỉ việc'}",
            )
            revoked_groups.append(grp.name)

        # Khóa tài khoản
        employee.user.is_active = False
        employee.user.save(update_fields=["is_active"])

    # ── Cập nhật Employee ─────────────────────────────────────────────────────
    employee.status = EmployeeStatus.TERMINATED if terminate else EmployeeStatus.RESIGNED
    employee.resignation_date = resignation_date or date.today()
    employee.save(update_fields=["status", "resignation_date", "updated_at"])

    # ── Ghi OFFBOARD log ──────────────────────────────────────────────────────
    AccessLog.objects.create(
        employee=employee,
        action=AccessLogAction.OFFBOARD,
        actor=actor,
        note=(
            f"Offboard bởi {actor.get_full_name() or actor.username}. "
            f"Lý do: {reason or 'Không ghi chú'}. "
            f"Nhóm thu hồi: {', '.join(revoked_groups) or '(không có)'}"
        ),
    )

    return employee
