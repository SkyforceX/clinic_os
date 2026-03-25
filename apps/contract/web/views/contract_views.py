from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.contract.domain.exceptions import (
    ContractPermissionDenied,
    ContractValidationError,
)
from apps.contract.policies import ContractPolicy
from apps.contract.selectors.checkup_overview import build_checkup_overview_payload
from apps.contract.selectors.contract_selectors import (
    get_contract_detail,
    get_contract_for_actor,
    list_contracts_for_user,
)
from apps.contract.services.approve_contract import execute as approve_contract_execute
from apps.contract.services.create_contract import (
    BloodCollectionRow as CreateBloodCollectionRow,
    CreateContractCommand,
    execute as create_contract_execute,
)
from apps.contract.services.delete_contract import execute as delete_contract_execute
from apps.contract.services.update_contract import (
    BloodCollectionRow as UpdateBloodCollectionRow,
    UpdateContractCommand,
    execute as update_contract_execute,
)
from apps.organizations.selectors.company_selectors import list_companies_for_actor


def _parse_blood_rows_from_post(request, row_cls):
    dates = request.POST.getlist("blood_collection_date[]") or []
    locs = request.POST.getlist("blood_location[]") or []
    people = request.POST.getlist("blood_people_count[]") or []
    staffs = request.POST.getlist("blood_staff_count[]") or []

    row_count = max(len(dates), len(locs), len(people), len(staffs))
    rows = []

    for i in range(row_count):
        rows.append(
            row_cls(
                collection_date=dates[i] if i < len(dates) else "",
                location=locs[i] if i < len(locs) else "",
                people_count=people[i] if i < len(people) else 0,
                staff_count=staffs[i] if i < len(staffs) else 0,
            )
        )

    return rows


@login_required(login_url="authentication:staff_login")
def contract_list(request):
    if not ContractPolicy.can_view_list(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    contracts = list_contracts_for_user(request.user)
    return render(
        request,
        "contract/staff/contract_list.html",
        {
            "contracts": contracts,
        },
    )


@login_required(login_url="authentication:staff_login")
def create_contract(request):
    companies = list_companies_for_actor(request.user)
    flag_nurse = ContractPolicy.is_nurse(request.user)

    return render(
        request,
        "contract/staff/create_contract.html",
        {
            "companies": companies,
            "flag_nurse": flag_nurse,
        },
    )


@login_required(login_url="authentication:staff_login")
@csrf_exempt
def save_contract(request):
    if request.method != "POST":
        return redirect("contract:contract_list")

    try:
        contract = create_contract_execute(
            CreateContractCommand(
                company_id=request.POST.get("company_id"),
                company_address=request.POST.get("company_address"),
                company_phone=request.POST.get("company_phone"),
                tax_code=request.POST.get("tax_code"),
                contact_person=request.POST.get("representative") or request.POST.get("contact_person"),
                representative_title=request.POST.get("representative_title"),
                employee_count=request.POST.get("employee_count"),
                start_date=request.POST.get("start_date"),
                end_date=request.POST.get("end_date"),
                reception_from_date=request.POST.get("reception_from_date"),
                contract_value_text=request.POST.get("contract_value_text"),
                deposit_payment_text=request.POST.get("deposit_payment_text"),
                settlement_time_text=request.POST.get("settlement_time_text"),
                note=request.POST.get("note"),
                blood_collection_rows=_parse_blood_rows_from_post(request, CreateBloodCollectionRow),
                actor=request.user,
            )
        )
        messages.success(request, f"Đã tạo lịch khám thành công ✅ ({contract.contract_number})")
    except ContractPermissionDenied as exc:
        messages.error(request, str(exc))
    except ContractValidationError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Đã xảy ra lỗi: {exc}")

    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
def edit_contract(request, contract_id):
    contract = get_contract_detail(user=request.user, contract_id=contract_id)
    if not contract:
        messages.error(request, "Không tìm thấy hợp đồng.")
        return redirect("contract:contract_list")

    if not ContractPolicy.can_update(request.user, contract):
        messages.error(request, "Bạn không có quyền sửa lịch khám này.")
        return redirect("contract:contract_list")

    companies = list_companies_for_actor(request.user)
    flag_nurse = ContractPolicy.is_nurse(request.user)

    if request.method == "POST":
        try:
            updated_contract = update_contract_execute(
                UpdateContractCommand(
                    contract_id=contract.id,
                    company_id=request.POST.get("company_id"),
                    company_address=request.POST.get("company_address"),
                    company_phone=request.POST.get("company_phone"),
                    tax_code=request.POST.get("tax_code"),
                    contact_person=request.POST.get("representative") or request.POST.get("contact_person"),
                    representative_title=request.POST.get("representative_title"),
                    employee_count=request.POST.get("employee_count"),
                    start_date=request.POST.get("start_date"),
                    end_date=request.POST.get("end_date"),
                    reception_from_date=request.POST.get("reception_from_date"),
                    contract_value_text=request.POST.get("contract_value_text"),
                    deposit_payment_text=request.POST.get("deposit_payment_text"),
                    settlement_time_text=request.POST.get("settlement_time_text"),
                    note=request.POST.get("note"),
                    blood_collection_rows=_parse_blood_rows_from_post(request, UpdateBloodCollectionRow),
                    actor=request.user,
                )
            )
            messages.success(request, "Đã cập nhật lịch khám thành công ✅")
            return redirect("contract:edit_contract", contract_id=updated_contract.id)
        except ContractPermissionDenied as exc:
            messages.error(request, str(exc))
        except ContractValidationError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Đã xảy ra lỗi: {exc}")

    return render(
        request,
        "contract/staff/edit_contract.html",
        {
            "contract": contract,
            "companies": companies,
            "flag_nurse": flag_nurse,
            "blood_collection_rows": getattr(contract, "blood_collection_rows", []),
        },
    )


@login_required(login_url="authentication:staff_login")
def approve_contract(request, contract_id):
    contract = get_contract_for_actor(user=request.user, contract_id=contract_id)
    if not contract:
        messages.error(request, "Không tìm thấy hợp đồng.")
        return redirect("contract:contract_list")

    try:
        approve_contract_execute(contract=contract, actor=request.user)
        messages.success(request, "Đã duyệt hợp đồng.")
    except ContractPermissionDenied as exc:
        messages.error(request, str(exc))
    except ContractValidationError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Lỗi duyệt hợp đồng: {exc}")

    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def delete_contract(request, contract_id):
    contract = get_contract_for_actor(user=request.user, contract_id=contract_id)
    if not contract:
        messages.error(request, "Không tìm thấy hợp đồng.")
        return redirect("contract:contract_list")

    try:
        delete_contract_execute(contract=contract, actor=request.user)
        messages.success(request, "Đã xóa hợp đồng thành công.")
    except ContractPermissionDenied as exc:
        messages.error(request, str(exc))
    except ContractValidationError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Lỗi xóa hợp đồng: {exc}")

    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_checkup_overview(request):
    company_id = request.POST.get("company_id")
    if not company_id:
        return JsonResponse({"success": False, "error": "Thiếu company_id"}, status=400)

    payload = build_checkup_overview_payload(user=request.user, company_id=company_id)
    return JsonResponse(payload, status=200)