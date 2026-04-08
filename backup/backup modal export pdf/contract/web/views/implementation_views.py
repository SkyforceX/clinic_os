from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.contract.models import Contract
from apps.contract.policies import ContractPolicy
from apps.contract.services.implementation_plans import (
    build_package_rows,
    build_sheet_year,
    export_plan_excel,
    get_or_create_plan,
    update_plan_rows_from_post,
)


def _implementation_contract_queryset():
    return (
        Contract.objects.select_related(
            "company",
            "created_by",
            "corporate_profile",
            "corporate_profile__quotation",
            "implementation_plan",
        )
        .prefetch_related(
            "service_lines",
            "blood_collection_schedules",
        )
        .filter(
            corporate_profile__isnull=False,
            is_locked=True,
        )
        .order_by("-locked_at", "-updated_at", "-id")
    )


def _get_contract_for_implementation(user, contract_id):
    contract = get_object_or_404(
        _implementation_contract_queryset(),
        pk=contract_id,
    )

    if not ContractPolicy.can_view_implementation(user):
        raise Http404("Bạn không có quyền xem kế hoạch triển khai này.")

    return contract


@login_required(login_url="authentication:staff_login")
@require_GET
def implementation_plan_list(request):
    if not ContractPolicy.can_view_implementation(request.user):
        raise Http404("Bạn không có quyền xem danh sách triển khai.")

    query = (request.GET.get("q") or "").strip()

    contracts = _implementation_contract_queryset()

    if query:
        contracts = contracts.filter(
            Q(contract_number__icontains=query)
            | Q(company__name__icontains=query)
            | Q(contact_person__icontains=query)
            | Q(corporate_profile__company_name_snapshot__icontains=query)
        )

    items = []
    for contract in contracts:
        plan = getattr(contract, "implementation_plan", None)
        items.append(
            {
                "contract": contract,
                "plan": plan,
                "can_view_contract_link": ContractPolicy.can_view_implementation_contract_link(
                    request.user,
                    contract,
                ),
                "can_edit_plan": ContractPolicy.can_edit_implementation(
                    request.user,
                    contract,
                ),
            }
        )

    context = {
        "items": items,
        "query": query,
        "total_items": len(items),
    }
    return render(
        request,
        "contract/staff/implementation_plan_list.html",
        context,
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def implementation_plan_detail(request, contract_id):
    contract = _get_contract_for_implementation(request.user, contract_id)
    plan = get_or_create_plan(contract)

    can_edit = ContractPolicy.can_edit_implementation(request.user, contract)
    can_view_contract_link = ContractPolicy.can_view_implementation_contract_link(
        request.user,
        contract,
    )

    if request.method == "POST":
        if not can_edit:
            messages.error(request, "Bạn không có quyền cập nhật kế hoạch triển khai.")
            return redirect("contract:implementation_plan_detail", contract_id=contract.id)

        update_plan_rows_from_post(plan, request.POST, contract)
        messages.success(request, "Đã lưu kế hoạch triển khai.")
        return redirect("contract:implementation_plan_detail", contract_id=contract.id)

    profile = getattr(contract, "corporate_profile", None)
    package_rows = build_package_rows(contract)

    company_name = ""
    if profile and getattr(profile, "company_name_snapshot", None):
        company_name = profile.company_name_snapshot
    elif contract.company:
        company_name = contract.company.name

    context = {
        "contract": contract,
        "profile": profile,
        "plan": plan,
        "plan_rows": plan.rows_json or [],
        "package_rows": package_rows,
        "plan_year": build_sheet_year(contract),
        "company_name": company_name,
        "can_edit_plan": can_edit,
        "can_view_contract_link": can_view_contract_link,
    }
    return render(request, "contract/staff/corporate_implementation_plan.html", context)


@login_required(login_url="authentication:staff_login")
@require_GET
def implementation_plan_export_excel(request, contract_id):
    contract = _get_contract_for_implementation(request.user, contract_id)
    plan = get_or_create_plan(contract)

    output, filename = export_plan_excel(contract, plan)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response