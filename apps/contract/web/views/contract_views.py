from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.contract.policies import ContractPolicy
from apps.contract.selectors.checkup_overview import build_checkup_overview_payload
from apps.contract.selectors.contract_selectors import (
    get_schedule_config_detail_for_user,
    list_quotations_for_schedule_user,
    list_schedule_configs_for_user,
)
from apps.core.models import SystemGeneralSetting
from apps.scheduling.services.contract_registration import (
    BloodCollectionInputRow,
    RegisterContractScheduleCommand,
    execute as register_contract_schedule_execute,
)
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.services.contract_lifecycle import delete_quote_schedule_config


def _parse_blood_rows_from_post(request):
    dates = request.POST.getlist("blood_collection_date[]") or []
    locs = request.POST.getlist("blood_location[]") or []
    people = request.POST.getlist("blood_people_count[]") or []
    staffs = request.POST.getlist("blood_staff_count[]") or []

    row_count = max(len(dates), len(locs), len(people), len(staffs))
    rows = []

    for i in range(row_count):
        rows.append(
            BloodCollectionInputRow(
                collection_date=dates[i] if i < len(dates) else "",
                location=locs[i] if i < len(locs) else "",
                people_count=people[i] if i < len(people) else 0,
                staff_count=staffs[i] if i < len(staffs) else 0,
            )
        )

    return rows


def _build_blood_rows_for_template_from_post(request):
    dates = request.POST.getlist("blood_collection_date[]") or []
    locs = request.POST.getlist("blood_location[]") or []
    people = request.POST.getlist("blood_people_count[]") or []
    staffs = request.POST.getlist("blood_staff_count[]") or []

    row_count = max(len(dates), len(locs), len(people), len(staffs), 1)
    rows = []

    for i in range(row_count):
        rows.append(
            {
                "collection_date": dates[i] if i < len(dates) else "",
                "location": locs[i] if i < len(locs) else "",
                "people_count": people[i] if i < len(people) else "",
                "staff_count": staffs[i] if i < len(staffs) else "",
            }
        )

    return rows


def _build_registration_context(*, user, config=None, old_post=None, old_blood_rows=None):
    settings = SystemGeneralSetting.get_solo()
    quotations = list_quotations_for_schedule_user(user)

    selected_quotation = getattr(config, "quotation", None) if config else None
    selected_contract = getattr(config, "contract", None) if config else None

    return {
        "available_quotations": quotations,
        "selected_config": config,
        "schedule_config": config,
        "selected_quotation": selected_quotation,
        "selected_contract": selected_contract,
        "blood_collection_rows": (
            old_blood_rows
            if old_blood_rows is not None
            else (getattr(config, "blood_collection_rows_list", []) if config else [])
        ),
        "default_am_limit": settings.default_am_slot_limit,
        "default_pm_limit": settings.default_pm_slot_limit,
        "system_setting": settings,
        "is_edit_mode": bool(config),
        "old_post": old_post,
                "can_delete_config": (
            bool(config)
            and not getattr(config, "contract_id", None)
            and SchedulingPolicy.can_manage_quote_schedule(
                user,
                getattr(getattr(config, "quotation", None), "created_by_id", None),
            )
        ),
    }


@login_required(login_url="authentication:staff_login")
def contract_list(request):
    if not ContractPolicy.can_view_list(request.user):
        raise Http404("Bạn không có quyền truy cập.")

    contracts = list_schedule_configs_for_user(request.user)
    return render(
        request,
        "contract/staff/contract_list.html",
        {
            "contracts": contracts,
        },
    )


@login_required(login_url="authentication:staff_login")
def create_contract(request):
    context = _build_registration_context(user=request.user)
    return render(request, "contract/staff/create_contract.html", context)


@login_required(login_url="authentication:staff_login")
@csrf_exempt
def save_contract(request):
    if request.method != "POST":
        return redirect("contract:contract_list")

    try:
        register_contract_schedule_execute(
            RegisterContractScheduleCommand(
                quotation_id=request.POST.get("quotation_id"),
                exam_start_date=request.POST.get("start_date"),
                exam_end_date=request.POST.get("end_date"),
                planned_employee_count=request.POST.get("employee_count"),
                am_capacity_limit=request.POST.get("am_capacity_limit"),
                pm_capacity_limit=request.POST.get("pm_capacity_limit"),
                blood_collection_rows=_parse_blood_rows_from_post(request),
                actor=request.user,
            )
        )
        messages.success(request, "Đã đăng ký lịch khám thành công ✅")
        return redirect("contract:contract_list")
    except Exception as exc:
        messages.error(request, f"Đã xảy ra lỗi: {exc}")
        context = _build_registration_context(
            user=request.user,
            old_post=request.POST,
            old_blood_rows=_build_blood_rows_for_template_from_post(request),
        )
        return render(request, "contract/staff/create_contract.html", context, status=400)


@login_required(login_url="authentication:staff_login")
def edit_contract(request, contract_id):
    config = get_schedule_config_detail_for_user(user=request.user, config_id=contract_id)
    if not config:
        messages.error(request, "Không tìm thấy lịch khám.")
        return redirect("contract:contract_list")

    if request.method == "POST":
        try:
            register_contract_schedule_execute(
                RegisterContractScheduleCommand(
                    quotation_id=config.quotation_id,
                    exam_start_date=request.POST.get("start_date"),
                    exam_end_date=request.POST.get("end_date"),
                    planned_employee_count=request.POST.get("employee_count"),
                    am_capacity_limit=request.POST.get("am_capacity_limit"),
                    pm_capacity_limit=request.POST.get("pm_capacity_limit"),
                    blood_collection_rows=_parse_blood_rows_from_post(request),
                    actor=request.user,
                )
            )
            messages.success(request, "Đã cập nhật đăng ký lịch khám thành công ✅")
            return redirect("contract:edit_contract", contract_id=config.id)
        except Exception as exc:
            messages.error(request, f"Đã xảy ra lỗi: {exc}")
            context = _build_registration_context(
                user=request.user,
                config=config,
                old_post=request.POST,
                old_blood_rows=_build_blood_rows_for_template_from_post(request),
            )
            return render(request, "contract/staff/create_contract.html", context, status=400)

    context = _build_registration_context(user=request.user, config=config)
    return render(request, "contract/staff/create_contract.html", context)


@login_required(login_url="authentication:staff_login")
def approve_contract(request, contract_id):
    messages.info(request, "Luồng duyệt này không còn áp dụng cho đăng ký lịch khám.")
    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def delete_contract(request, contract_id):
    try:
        delete_quote_schedule_config(actor=request.user, config_id=contract_id)
        messages.success(request, "Đã xóa lịch đăng ký khám thành công ✅")
    except PermissionError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Đã xảy ra lỗi: {exc}")

    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_checkup_overview(request):
    company_id = request.POST.get("company_id")
    if not company_id:
        return JsonResponse({"success": False, "error": "Thiếu company_id"}, status=400)

    payload = build_checkup_overview_payload(user=request.user, company_id=company_id)
    return JsonResponse(payload, status=200)