"""
apps.hrm.selectors.employee_selectors
─────────────────────────────────────
Query helpers cho Employee. Views và API chỉ gọi qua đây,
không gọi ORM trực tiếp.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.hrm.models.employee import Employee, EmployeeStatus


def list_employees(
    *,
    search: str = "",
    department_id: int | None = None,
    status: str | None = None,
    position_id: int | None = None,
) -> QuerySet[Employee]:
    """
    Danh sách nhân viên với filter tùy chọn.
    Luôn select_related để tránh N+1 trong template.
    """
    qs = Employee.objects.select_related(
        "department", "position", "direct_manager", "user"
    )

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(employee_code__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        )

    if department_id:
        qs = qs.filter(department_id=department_id)

    if status:
        qs = qs.filter(status=status)
    else:
        # Mặc định chỉ hiện nhân viên đang làm
        qs = qs.filter(
            status__in=[EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION, EmployeeStatus.ON_LEAVE]
        )

    if position_id:
        qs = qs.filter(position_id=position_id)

    return qs.order_by("full_name")


def get_employee_by_pk(pk: int) -> Employee | None:
    try:
        return Employee.objects.select_related(
            "department", "position", "direct_manager", "user", "created_by"
        ).get(pk=pk)
    except Employee.DoesNotExist:
        return None


def get_employee_for_user(user) -> Employee | None:
    """Lấy hồ sơ nhân viên của user đang đăng nhập."""
    try:
        return Employee.objects.select_related(
            "department", "position", "direct_manager"
        ).get(user=user)
    except Employee.DoesNotExist:
        return None


def list_active_employees_for_select() -> QuerySet[Employee]:
    """Dùng cho dropdown chọn nhân viên trong form."""
    return (
        Employee.objects.filter(
            status__in=[EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION]
        )
        .select_related("department", "position")
        .order_by("full_name")
    )
