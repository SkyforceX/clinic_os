import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
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
from apps.his_integration.models import HisCorporatePackageSync
from apps.scheduling.models import ScheduleBloodCollectionRow, SpecialExamCategory
from apps.scheduling.services.contract_registration import (
    BloodCollectionInputRow,
    RegisterContractScheduleCommand,
    execute as register_contract_schedule_execute,
)
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.services.contract_lifecycle import delete_quote_schedule_config


def _can_assign_his_package(user) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    return user.groups.filter(name__in=[
        "Operations Team", "Operations", "VH", "Vận hành", "Van hanh",
        "IT Admin", "IT", "IT Support",
    ]).exists()


def _get_actual_contract(config):
    """ContractScheduleConfig → CorporateContractProfile → Contract."""
    return getattr(getattr(config, "contract", None), "contract", None)


def _link_his_package(his_package_id, config):
    from apps.scheduling.models.schedule import ContractScheduleConfig
    pkg_id = int(his_package_id) if his_package_id else None
    if config and config.his_package_id != pkg_id:
        ContractScheduleConfig.objects.filter(pk=config.pk).update(his_package_id=pkg_id)


def _save_special_exam_categories(category_id_list, config):
    if not config:
        return
    ids = [int(x) for x in category_id_list if str(x).isdigit()]
    categories = SpecialExamCategory.objects.filter(pk__in=ids, is_active=True)
    config.special_exam_categories.set(categories)


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


def _parse_date_for_template(raw):
    from datetime import datetime
    if not raw:
        return ""
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return raw


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
                "collection_date": _parse_date_for_template(dates[i] if i < len(dates) else ""),
                "location": locs[i] if i < len(locs) else "",
                "people_count": people[i] if i < len(people) else "",
                "staff_count": staffs[i] if i < len(staffs) else "",
            }
        )

    return rows


def _build_blood_date_counts_json(config):
    """Trả về JSON: {date_iso: count} của địa điểm lấy máu từ các config KHÁC."""
    qs = ScheduleBloodCollectionRow.objects.values("collection_date").annotate(count=Count("id"))
    if config:
        qs = qs.exclude(schedule_config=config)
    return json.dumps({item["collection_date"].isoformat(): item["count"] for item in qs})


def _build_registration_context(*, user, config=None, old_post=None, old_blood_rows=None):
    settings = SystemGeneralSetting.get_solo()
    quotations = list_quotations_for_schedule_user(user)

    selected_quotation = getattr(config, "quotation", None) if config else None
    selected_contract = getattr(config, "contract", None) if config else None

    linked_his_package = getattr(config, "his_package", None) if config else None

    config_allowed_weekdays = list(getattr(config, "allowed_weekdays", None) or []) if config else []

    if old_post is not None:
        raw = old_post.getlist("allowed_weekday") if hasattr(old_post, "getlist") else []
        preselected_weekdays = [int(x) for x in raw if str(x).isdigit()]
    else:
        preselected_weekdays = config_allowed_weekdays

    weekday_choices = [
        (0, "Thứ 2"),
        (1, "Thứ 3"),
        (2, "Thứ 4"),
        (3, "Thứ 5"),
        (4, "Thứ 6"),
        (5, "Thứ 7"),
    ]

    all_special_exam_categories = SpecialExamCategory.objects.filter(is_active=True)
    if old_post is not None:
        selected_cat_ids = set(int(x) for x in old_post.getlist("special_exam_category_ids") if str(x).isdigit())
    elif config:
        selected_cat_ids = set(config.special_exam_categories.values_list("id", flat=True))
    else:
        selected_cat_ids = set()

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
        "is_view_mode": bool(config) and getattr(config, "is_confirmed", False),
        "old_post": old_post,
        "config_allowed_weekdays": config_allowed_weekdays,
        "preselected_weekdays": preselected_weekdays,
        "weekday_choices": weekday_choices,
        "available_his_packages": (
            HisCorporatePackageSync.objects
            .filter(is_active=True)
            .order_by("company_name", "package_name")
        ),
        "linked_his_package": linked_his_package,
        "can_delete_config": (
            bool(config)
            and not getattr(config, "contract_id", None)
            and SchedulingPolicy.can_manage_quote_schedule(
                user,
                getattr(getattr(config, "quotation", None), "created_by_id", None),
            )
        ),
        "can_end_schedule": (
            bool(config)
            and getattr(config, "is_confirmed", False)
            and not getattr(config, "is_ended", False)
            and SchedulingPolicy.can_end_schedule(
                user,
                getattr(getattr(config, "quotation", None), "created_by_id", None),
            )
        ),
        "is_ended": bool(config) and getattr(config, "is_ended", False),
        "can_assign_his_package": _can_assign_his_package(user),
        "max_blood_per_day": settings.max_blood_location_per_day,
        "blood_date_counts_json": _build_blood_date_counts_json(config),
        "special_exam_categories": all_special_exam_categories,
        "selected_special_exam_category_ids": selected_cat_ids,
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
        config = register_contract_schedule_execute(
            RegisterContractScheduleCommand(
                quotation_id=request.POST.get("quotation_id"),
                exam_start_date=request.POST.get("start_date"),
                exam_end_date=request.POST.get("end_date"),
                planned_employee_count=request.POST.get("employee_count"),
                am_capacity_limit=request.POST.get("am_capacity_limit"),
                pm_capacity_limit=request.POST.get("pm_capacity_limit"),
                blood_collection_rows=_parse_blood_rows_from_post(request),
                allowed_weekdays=request.POST.getlist("allowed_weekday"),
                actor=request.user,
            )
        )
        if _can_assign_his_package(request.user):
            _link_his_package(request.POST.get("his_package_id"), config)
        _save_special_exam_categories(request.POST.getlist("special_exam_category_ids"), config)
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
            updated_config = register_contract_schedule_execute(
                RegisterContractScheduleCommand(
                    quotation_id=config.quotation_id,
                    exam_start_date=request.POST.get("start_date"),
                    exam_end_date=request.POST.get("end_date"),
                    planned_employee_count=request.POST.get("employee_count"),
                    am_capacity_limit=request.POST.get("am_capacity_limit"),
                    pm_capacity_limit=request.POST.get("pm_capacity_limit"),
                    blood_collection_rows=_parse_blood_rows_from_post(request),
                    allowed_weekdays=request.POST.getlist("allowed_weekday"),
                    actor=request.user,
                )
            )
            if _can_assign_his_package(request.user):
                _link_his_package(request.POST.get("his_package_id"), updated_config)
            _save_special_exam_categories(request.POST.getlist("special_exam_category_ids"), updated_config)
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
def confirm_contract(request, contract_id):
    from django.utils import timezone
    from apps.scheduling.models.schedule import ContractScheduleConfig
    from apps.scheduling.policies import SchedulingPolicy

    config = ContractScheduleConfig.objects.filter(pk=contract_id).first()
    if not config:
        messages.error(request, "Không tìm thấy lịch đăng ký khám.")
        return redirect("contract:contract_list")

    owner_id = getattr(getattr(config, "quotation", None), "created_by_id", None)
    if not SchedulingPolicy.can_manage_quote_schedule(request.user, owner_id):
        messages.error(request, "Bạn không có quyền chốt lịch khám này.")
        return redirect("contract:contract_list")

    if config.is_confirmed:
        messages.warning(request, "Lịch khám này đã được chốt trước đó.")
        return redirect("contract:contract_list")

    config.is_confirmed = True
    config.confirmed_by = request.user
    config.confirmed_at = timezone.now()
    config.save(update_fields=["is_confirmed", "confirmed_by", "confirmed_at", "updated_at"])

    messages.success(request, "Đã chốt lịch khám thành công ✅")
    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def unconfirm_contract(request, contract_id):
    from apps.scheduling.models.schedule import ContractScheduleConfig

    if not SchedulingPolicy.is_it_staff(request.user):
        messages.error(request, "Chỉ IT staff mới có thể gỡ chốt lịch khám.")
        return redirect("contract:contract_list")

    config = ContractScheduleConfig.objects.filter(pk=contract_id).first()
    if not config:
        messages.error(request, "Không tìm thấy lịch đăng ký khám.")
        return redirect("contract:contract_list")

    if not config.is_confirmed:
        messages.warning(request, "Lịch khám này chưa được chốt.")
        return redirect("contract:contract_list")

    if config.is_ended:
        messages.error(request, "Không thể gỡ chốt lịch khám đã kết thúc.")
        return redirect("contract:contract_list")

    config.is_confirmed = False
    config.confirmed_by = None
    config.confirmed_at = None
    config.save(update_fields=["is_confirmed", "confirmed_by", "confirmed_at", "updated_at"])

    messages.success(request, "Đã gỡ chốt lịch khám thành công.")
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