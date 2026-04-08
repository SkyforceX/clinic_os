from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.hrm.exceptions import HRMPermissionDenied, HRMValidationError
from apps.hrm.models.employee import Employee, EmployeeStatus
from apps.hrm.models.access_control import AccessLog
from apps.hrm.models.department import Department, Position
from apps.hrm.policies import HRMPolicy
from apps.hrm.selectors.employee_selectors import (
    get_employee_by_pk,
    list_employees,
)
from apps.hrm.services import grant_access as grant_access_svc
from apps.hrm.services import offboard as offboard_svc
from apps.hrm.web.forms import EmployeeForm, OffboardForm, TransferForm

LOGIN_URL = "authentication:staff_login"

def _employee_position_options():
    return [
        {
            "id": position.pk,
            "name": position.name,
            "department_id": position.department_id,
        }
        for position in Position.objects.filter(
            is_active=True,
            department__is_active=True,
        )
        .select_related("department")
        .order_by("department__display_order", "-level", "name")
    ]

# ── Danh sách nhân viên ───────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def employee_list(request):
    if not HRMPolicy.can_view_employee_list(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    search        = request.GET.get("q", "").strip()
    department_id = request.GET.get("department_id") or None
    status_filter = request.GET.get("status") or None

    employees = list_employees(
        search=search,
        department_id=int(department_id) if department_id else None,
        status=status_filter,
    )
    departments = Department.objects.filter(is_active=True).order_by("name")

    return render(request, "hrm/staff/employee_list.html", {
        "employees":      employees,
        "departments":    departments,
        "search":         search,
        "department_id":  department_id,
        "status_filter":  status_filter,
        "status_choices": EmployeeStatus.choices,
        "total_count":    employees.count(),
    })


# ── Chi tiết nhân viên ────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def employee_detail(request, employee_id: int):
    employee = get_employee_by_pk(employee_id)
    if not employee:
        raise Http404("Không tìm thấy nhân viên.")
    if not HRMPolicy.can_view_employee(request.user, employee):
        raise Http404("Bạn không có quyền xem hồ sơ này.")

    access_logs = (
        AccessLog.objects.filter(employee=employee)
        .select_related("django_group", "actor")
        .order_by("-created_at")[:20]
    )

    # Nhóm quyền hiện tại
    current_groups = (
        list(employee.user.groups.values_list("name", flat=True))
        if employee.user
        else []
    )

    return render(request, "hrm/staff/employee_detail.html", {
        "employee":       employee,
        "access_logs":    access_logs,
        "current_groups": current_groups,
        "can_edit":       HRMPolicy.can_update_employee(request.user),
        "can_offboard":   HRMPolicy.can_offboard(request.user),
        "can_transfer":   HRMPolicy.can_transfer(request.user),
    })


# ── Tạo nhân viên ─────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def employee_create(request):
    if not HRMPolicy.can_create_employee(request.user):
        raise Http404("Bạn không có quyền tạo hồ sơ nhân viên.")

    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.created_by = request.user
            # Tạo trực tiếp (không qua onboard service) nếu không cần tạo User
            employee.save()
            # Cấp quyền theo chức vụ nếu đã có position
            if employee.position:
                grant_access_svc.grant_access_by_position(
                    employee=employee, actor=request.user
                )
            messages.success(request, f"Đã tạo hồ sơ nhân viên {employee.full_name}.")
            return redirect("hrm:employee_detail", employee_id=employee.pk)
    else:
        form = EmployeeForm()

    return render(request, "hrm/staff/employee_form.html", {
        "form": form,
        "form_title": "Tạo hồ sơ nhân viên mới",
        "submit_label": "Tạo nhân viên",
        "position_options": _employee_position_options(),
    })


# ── Sửa nhân viên ─────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def employee_edit(request, employee_id: int):
    if not HRMPolicy.can_update_employee(request.user):
        raise Http404("Bạn không có quyền chỉnh sửa.")

    employee = get_object_or_404(Employee, pk=employee_id)

    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật hồ sơ nhân viên.")
            return redirect("hrm:employee_detail", employee_id=employee.pk)
    else:
        form = EmployeeForm(instance=employee)

    return render(request, "hrm/staff/employee_form.html", {
        "form": form,
        "employee": employee,
        "form_title": f"Sửa hồ sơ – {employee.full_name}",
        "submit_label": "Lưu thay đổi",
        "position_options": _employee_position_options(),
    })


# ── Chuyển bộ phận / chức vụ ─────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def employee_transfer(request, employee_id: int):
    if not HRMPolicy.can_transfer(request.user):
        raise Http404("Bạn không có quyền thực hiện chuyển bộ phận.")

    employee = get_object_or_404(Employee, pk=employee_id)

    if request.method == "POST":
        form = TransferForm(request.POST)
        if form.is_valid():
            try:
                result = grant_access_svc.sync_access_on_transfer(
                    employee=employee,
                    new_position=form.cleaned_data["new_position"],
                    new_department=form.cleaned_data.get("new_department"),
                    actor=request.user,
                    note=form.cleaned_data.get("note", ""),
                )
                messages.success(
                    request,
                    f"Đã chuyển bộ phận. "
                    f"Thu hồi: {', '.join(result['revoked']) or '(không có)'}. "
                    f"Cấp mới: {', '.join(result['granted']) or '(không có)'}.",
                )
                return redirect("hrm:employee_detail", employee_id=employee.pk)
            except HRMValidationError as e:
                messages.error(request, str(e))
    else:
        form = TransferForm(initial={
            "new_position":   employee.position,
            "new_department": employee.department,
        })

    return render(request, "hrm/staff/employee_transfer.html", {
        "form":     form,
        "employee": employee,
    })


# ── Nghỉ việc ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def employee_offboard(request, employee_id: int):
    if not HRMPolicy.can_offboard(request.user):
        raise Http404("Bạn không có quyền thực hiện nghỉ việc.")

    employee = get_object_or_404(Employee, pk=employee_id)

    if request.method == "POST":
        form = OffboardForm(request.POST)
        if form.is_valid():
            try:
                offboard_svc.execute(
                    employee=employee,
                    actor=request.user,
                    resignation_date=form.cleaned_data["resignation_date"],
                    reason=form.cleaned_data.get("reason", ""),
                    terminate=form.cleaned_data.get("terminate", False),
                )
                messages.success(request, f"{employee.full_name} đã được xử lý nghỉ việc.")
                return redirect("hrm:employee_detail", employee_id=employee.pk)
            except (HRMPermissionDenied, HRMValidationError) as e:
                messages.error(request, str(e))
    else:
        form = OffboardForm()

    return render(request, "hrm/staff/employee_offboard.html", {
        "form":     form,
        "employee": employee,
    })
