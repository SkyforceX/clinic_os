from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.organizations.policies import OrganizationPolicy
from apps.organizations.selectors.company_selectors import (
    get_company_for_actor,
    list_companies_for_actor,
)
from apps.organizations.services.company_commands import (
    CompanyPayload,
    OrganizationPermissionDenied,
    OrganizationValidationError,
    create_company,
    delete_company,
    update_company,
)
from apps.organizations.web.forms import CompanyForm
from apps.patients.models import Patient


def _require_company_access(request, company_id):
    company = get_company_for_actor(user=request.user, company_id=company_id)
    if not company:
        raise Http404("Không tìm thấy công ty.")
    return company


def _company_list_url(company_id=None):
    base = reverse("organizations:company_list")
    if company_id:
        return f"{base}?company_id={company_id}"
    return base


@login_required(login_url="authentication:staff_login")
def company_list_view(request):
    if not OrganizationPolicy.can_view_list(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    companies = list_companies_for_actor(request.user)
    selected_company_id = request.GET.get("company_id")
    selected_company = None
    patients = []

    if selected_company_id:
        try:
            selected_company = get_company_for_actor(
                user=request.user,
                company_id=int(selected_company_id),
            )
        except (TypeError, ValueError):
            selected_company = None

        if selected_company:
            patients = Patient.objects.filter(
                company_id=selected_company.id
            ).order_by("id")
    
    context = {
        "companies": companies,
        "patients": patients,
        "selected_company_id": str(selected_company.id) if selected_company else "",
        "is_manager": OrganizationPolicy.is_manager(request.user),
    }
    return render(request, "organizations/staff/company_list.html", context)


@login_required(login_url="authentication:staff_login")
def company_create_view(request):
    if request.method != "POST":
        return redirect("organizations:company_list")

    form = CompanyForm(request.POST)
    if not form.is_valid():
        for _, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect("organizations:company_list")

    try:
        create_company(
            actor=request.user,
            payload=CompanyPayload(
                name=form.cleaned_data["name"],
                address=form.cleaned_data["address"],
                tax_code=form.cleaned_data["tax_code"],
                phone=form.cleaned_data["phone"],
            ),
        )
        messages.success(request, "Đã tạo công ty mới.")
    except OrganizationValidationError as exc:
        messages.error(request, str(exc))
    except OrganizationPermissionDenied as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Lỗi khi tạo công ty: {exc}")

    return redirect("organizations:company_list")


@login_required(login_url="authentication:staff_login")
def company_update_view(request, company_id):
    company = _require_company_access(request, company_id)

    if request.method != "POST":
        return redirect(_company_list_url(company.id))

    form = CompanyForm(request.POST, instance=company)
    if not form.is_valid():
        for _, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect(_company_list_url(company.id))

    try:
        update_company(
            actor=request.user,
            company=company,
            payload=CompanyPayload(
                name=form.cleaned_data["name"],
                address=form.cleaned_data["address"],
                tax_code=form.cleaned_data["tax_code"],
                phone=form.cleaned_data["phone"],
            ),
        )
        messages.success(request, "Đã cập nhật công ty.")
    except OrganizationValidationError as exc:
        messages.error(request, str(exc))
    except OrganizationPermissionDenied as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Lỗi khi cập nhật công ty: {exc}")

    return redirect(_company_list_url(company.id))


@login_required(login_url="authentication:staff_login")
def company_delete_view(request, company_id):
    company = _require_company_access(request, company_id)

    if request.method != "POST":
        return redirect("organizations:company_list")

    try:
        delete_company(actor=request.user, company=company)
        messages.success(request, "Đã xóa công ty.")
    except OrganizationValidationError as exc:
        messages.error(request, str(exc))
    except OrganizationPermissionDenied as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Lỗi khi xóa công ty: {exc}")

    return redirect("organizations:company_list")


@login_required(login_url="authentication:staff_login")
def company_options_json(request):
    companies = list_companies_for_actor(request.user)
    data = [
        {
            "id": company.id,
            "uuid": str(company.uuid),
            "name": company.name,
            "address": company.address or "",
            "tax_code": company.tax_code or "",
            "phone": company.phone or "",
        }
        for company in companies
    ]
    return JsonResponse({"results": data})