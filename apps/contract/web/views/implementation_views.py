from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.contract.models import ACTIVE_STATUSES, Contract
from apps.contract.policies import ContractPolicy
from apps.contract.services.implementation_plans import (
    build_package_rows,
    build_plan_log_entries,
    build_plan_rows_for_display,
    build_sheet_year,
    confirm_plan_row,
    export_plan_excel,
    get_or_create_plan,
    unlock_plan_row,
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
            "implementation_plan__logs",
        )
        .filter(
            corporate_profile__isnull=False,
        )
        .filter(
            Q(is_locked=True) | Q(status__in=ACTIVE_STATUSES)
        )
        .order_by("-approved_at", "-locked_at", "-updated_at", "-id")
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
    can_view_logs = ContractPolicy.can_view_implementation_logs(request.user, contract)
    can_manage_unlock = ContractPolicy.can_manage_implementation_unlock(request.user, contract)
    is_executive = ContractPolicy.is_executive(request.user)

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        row_stt = request.POST.get("row_stt")
        department_key = (request.POST.get("department_key") or "").strip()

        try:
            if action == "save":
                if not can_edit:
                    messages.error(request, "Bạn không có quyền cập nhật kế hoạch triển khai.")
                else:
                    update_plan_rows_from_post(plan, request.POST, contract, actor=request.user)
                    messages.success(request, "Đã lưu kế hoạch triển khai.")

            elif action == "confirm":
                if can_edit or is_executive or request.user.is_superuser:
                    messages.error(request, "Tài khoản theo dõi tiến độ không được bấm xác nhận.")
                else:
                    changed, row = confirm_plan_row(
                        plan,
                        contract,
                        row_stt=row_stt,
                        department_key=department_key,
                        actor=request.user,
                    )
                    if changed:
                        messages.success(
                            request,
                            f"Đã xác nhận dòng {row.get('stt')} - {row.get('category')} cho phòng ban {department_key}.",
                        )
                    else:
                        messages.info(request, "Dòng này đã được xác nhận trước đó.")

            elif action == "unlock":
                if not can_manage_unlock:
                    messages.error(request, "Bạn không có quyền gỡ xác nhận / mở khóa dòng này.")
                else:
                    changed, row = unlock_plan_row(
                        plan,
                        contract,
                        row_stt=row_stt,
                        actor=request.user,
                    )
                    if changed:
                        messages.success(
                            request,
                            f"Đã gỡ toàn bộ xác nhận và mở khóa dòng {row.get('stt')} - {row.get('category')}.",
                        )
                    else:
                        messages.info(request, "Dòng này chưa có xác nhận để gỡ.")
            else:
                messages.error(request, "Thao tác không hợp lệ.")
        except ValueError as exc:
            messages.error(request, str(exc))

        return redirect("contract:implementation_plan_detail", contract_id=contract.id)

    profile = getattr(contract, "corporate_profile", None)
    package_rows = build_package_rows(contract)

    company_name = ""
    if profile and getattr(profile, "company_name_snapshot", None):
        company_name = profile.company_name_snapshot
    elif contract.company:
        company_name = contract.company.name

    plan_rows = build_plan_rows_for_display(
        plan,
        contract,
        request.user,
        can_edit=can_edit,
        is_executive=is_executive,
    )
    log_entries = []
    if can_view_logs:
        log_entries = build_plan_log_entries(plan.logs.select_related("actor").all())

    context = {
        "contract": contract,
        "profile": profile,
        "plan": plan,
        "plan_rows": plan_rows,
        "package_rows": package_rows,
        "plan_year": build_sheet_year(contract),
        "company_name": company_name,
        "can_edit_plan": can_edit,
        "can_view_contract_link": can_view_contract_link,
        "can_view_logs": can_view_logs,
        "can_manage_unlock": can_manage_unlock,
        "is_executive": is_executive,
        "log_entries": log_entries,
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
