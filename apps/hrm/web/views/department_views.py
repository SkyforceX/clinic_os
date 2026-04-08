from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.hrm.models.department import Department, Position
from apps.hrm.policies import HRMPolicy
from apps.hrm.web.forms import DepartmentForm, PositionForm

LOGIN_URL = "authentication:staff_login"


# ── Phòng ban ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def department_list(request):
    if not HRMPolicy.can_manage_departments(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    departments = Department.objects.select_related("parent").order_by("display_order", "name")
    return render(request, "hrm/staff/department_list.html", {
        "departments": departments,
    })


@login_required(login_url=LOGIN_URL)
def department_create(request):
    if not HRMPolicy.can_manage_departments(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save()
            messages.success(request, f"Đã tạo phòng ban '{dept.name}'.")
            return redirect("hrm:department_list")
    else:
        form = DepartmentForm()

    return render(request, "hrm/staff/department_form.html", {
        "form": form,
        "form_title": "Tạo phòng ban mới",
    })


@login_required(login_url=LOGIN_URL)
def department_edit(request, department_id: int):
    if not HRMPolicy.can_manage_departments(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    dept = get_object_or_404(Department, pk=department_id)

    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật phòng ban.")
            return redirect("hrm:department_list")
    else:
        form = DepartmentForm(instance=dept)

    return render(request, "hrm/staff/department_form.html", {
        "form":       form,
        "department": dept,
        "form_title": f"Sửa phòng ban – {dept.name}",
    })


# ── Chức vụ ───────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def position_list(request):
    if not HRMPolicy.can_manage_positions(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    positions = Position.objects.select_related("department").order_by("-level", "name")
    return render(request, "hrm/staff/position_list.html", {
        "positions": positions,
    })


@login_required(login_url=LOGIN_URL)
def position_create(request):
    if not HRMPolicy.can_manage_positions(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    if request.method == "POST":
        form = PositionForm(request.POST)
        if form.is_valid():
            pos = form.save()
            messages.success(request, f"Đã tạo chức vụ '{pos.name}'.")
            return redirect("hrm:position_list")
    else:
        form = PositionForm()

    return render(request, "hrm/staff/position_form.html", {
        "form": form,
        "form_title": "Tạo chức vụ mới",
    })


@login_required(login_url=LOGIN_URL)
def position_edit(request, position_id: int):
    if not HRMPolicy.can_manage_positions(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    pos = get_object_or_404(Position, pk=position_id)

    if request.method == "POST":
        form = PositionForm(request.POST, instance=pos)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật chức vụ.")
            return redirect("hrm:position_list")
    else:
        form = PositionForm(instance=pos)

    return render(request, "hrm/staff/position_form.html", {
        "form":       form,
        "position":   pos,
        "form_title": f"Sửa chức vụ – {pos.name}",
    })
