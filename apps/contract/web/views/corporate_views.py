from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.contract.models import Contract
from apps.contract.models.contract import CLOSED_STATUSES
from apps.contract.policies import ContractPolicy
from apps.contract.services.corporate_contracts import (
    build_catalog_groups,
    build_quote_context,
    create_corporate_contract_from_request,
)
from apps.organizations.selectors.company_selectors import list_companies_for_actor


@login_required(login_url="authentication:staff_login")
def create_corporate_contract(request):
    from apps.contract.models.quotation import QuotationDraft
    companies = list_companies_for_actor(request.user)
    flag_nurse = ContractPolicy.is_nurse(request.user)
    catalog_groups = build_catalog_groups()
    quotations = QuotationDraft.objects.order_by("-created_at")[:50]

    return render(
        request,
        "contract/staff/create_corporate_contract.html",
        {
            "companies": companies,
            "flag_nurse": flag_nurse,
            "catalog_groups": catalog_groups,
            "quotations": quotations,
        },
    )


@login_required(login_url="authentication:staff_login")
@csrf_exempt
def save_corporate_contract(request):
    if request.method != "POST":
        return redirect("contract:corporate_contract_list")

    try:
        contract = create_corporate_contract_from_request(request)
        messages.success(request, "Đã tạo hợp đồng doanh nghiệp và lịch khám thành công ✅")
        return redirect("contract:corporate_quote_print", contract_id=contract.id)
    except ValidationError as exc:
        messages.error(request, f"Lỗi nhập liệu: {exc}")
    except IntegrityError as exc:
        messages.error(request, f"Lỗi dữ liệu: {exc}")
    except Exception as exc:
        messages.error(request, f"Đã xảy ra lỗi: {exc}")

    return redirect("contract:create_corporate_contract")


@login_required(login_url="authentication:staff_login")
def corporate_contract_list(request):
    today = timezone.now().date()
    expired_date = today - timedelta(days=21)

    qs = Contract.objects.select_related(
        "company",
        "created_by",
        "corporate_profile",
    ).filter(corporate_profile__isnull=False)

    if ContractPolicy.is_manager(request.user):
        contracts = qs.order_by("-created_at")
    else:
        contracts = qs.exclude(
            status__in=CLOSED_STATUSES,
        ).filter(
            created_at__date__gt=expired_date,
            created_by=request.user,
        ).order_by("-created_at")

    return render(
        request,
        "contract/staff/corporate_contract_list.html",
        {"contracts": contracts},
    )


@login_required(login_url="authentication:staff_login")
def corporate_quote_print(request, contract_id):
    contract = get_object_or_404(
        Contract.objects.select_related("company", "corporate_profile", "created_by"),
        pk=contract_id,
        corporate_profile__isnull=False,
    )

    if not (
        ContractPolicy.is_manager(request.user)
        or contract.created_by_id == request.user.id
    ):
        messages.error(request, "Bạn không có quyền xem báo giá này.")
        return redirect("contract:corporate_contract_list")

    context = build_quote_context(contract)
    return render(request, "contract/staff/corporate_quote_print.html", context)


@login_required(login_url="authentication:staff_login")
def corporate_contract_print(request, contract_id):
    contract = get_object_or_404(
        Contract.objects.select_related("company", "corporate_profile", "created_by"),
        pk=contract_id,
        corporate_profile__isnull=False,
    )

    if not (
        ContractPolicy.is_manager(request.user)
        or contract.created_by_id == request.user.id
    ):
        messages.error(request, "Bạn không có quyền xem hợp đồng này.")
        return redirect("contract:corporate_contract_list")

    context = build_quote_context(contract)
    return render(request, "contract/staff/corporate_contract_print.html", context)