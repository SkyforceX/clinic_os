"""
apps.hrm.services.grant_access
──────────────────────────────
Cấp / thu hồi Django Group cho User dựa theo PositionGroupMapping.

API công khai:
    grant_access_by_position(employee, actor)
    revoke_access_by_position(employee, actor)
    sync_access_on_transfer(employee, new_position, new_department, actor)
"""

from __future__ import annotations

from django.db import transaction

from apps.hrm.exceptions import HRMValidationError
from apps.hrm.models.access_control import AccessLog, AccessLogAction, PositionGroupMapping


def _log(employee, action: str, group=None, actor=None, note: str = "") -> None:
    AccessLog.objects.create(
        employee=employee,
        action=action,
        django_group=group,
        actor=actor,
        note=note,
    )


@transaction.atomic
def grant_access_by_position(*, employee, actor=None) -> list[str]:
    """
    Đọc PositionGroupMapping theo chức vụ hiện tại của employee
    rồi gán Django Group tương ứng vào User.

    Bỏ qua nếu employee chưa có user liên kết.
    Trả về list tên Group đã gán.
    """
    if employee.user is None:
        return []
    if employee.position is None:
        return []

    mappings = PositionGroupMapping.objects.filter(
        position=employee.position
    ).select_related("django_group")

    granted = []
    for m in mappings:
        employee.user.groups.add(m.django_group)
        _log(
            employee,
            AccessLogAction.GRANTED,
            group=m.django_group,
            actor=actor,
            note=f"Cấp theo chức vụ: {employee.position.name}",
        )
        granted.append(m.django_group.name)

    return granted


@transaction.atomic
def revoke_access_by_position(*, employee, actor=None, position=None) -> list[str]:
    """
    Thu hồi tất cả Django Group được map từ chức vụ hiện tại
    (hoặc chức vụ được truyền vào nếu đang chuyển bộ phận).

    Trả về list tên Group đã thu hồi.
    """
    if employee.user is None:
        return []

    target_position = position or employee.position
    if target_position is None:
        return []

    mappings = PositionGroupMapping.objects.filter(
        position=target_position
    ).select_related("django_group")

    revoked = []
    for m in mappings:
        employee.user.groups.remove(m.django_group)
        _log(
            employee,
            AccessLogAction.REVOKED,
            group=m.django_group,
            actor=actor,
            note=f"Thu hồi khỏi chức vụ: {target_position.name}",
        )
        revoked.append(m.django_group.name)

    return revoked


@transaction.atomic
def sync_access_on_transfer(
    *,
    employee,
    new_position,
    new_department=None,
    actor=None,
    note: str = "",
) -> dict:
    """
    Chuyển bộ phận / chức vụ:
      1. Thu hồi Group từ chức vụ CŨ
      2. Cập nhật position / department trên Employee
      3. Cấp Group theo chức vụ MỚI
      4. Ghi AccessLog(TRANSFER)

    Trả về {"revoked": [...], "granted": [...]}
    """
    if new_position is None:
        raise HRMValidationError("Chức vụ mới không được để trống.")

    old_position = employee.position

    revoked = revoke_access_by_position(
        employee=employee, actor=actor, position=old_position
    )

    employee.position = new_position
    if new_department is not None:
        employee.department = new_department
    employee.save(update_fields=["position", "department", "updated_at"])

    granted = grant_access_by_position(employee=employee, actor=actor)

    _log(
        employee,
        AccessLogAction.TRANSFER,
        actor=actor,
        note=note or (
            f"Chuyển từ [{old_position}] → [{new_position}] "
            f"| Bộ phận: [{new_department or employee.department}]"
        ),
    )

    return {"revoked": revoked, "granted": granted}
