import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import SystemGeneralSetting
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType, TimeShift
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_matrix import build_contract_schedule_matrix
from apps.scheduling.selectors.slot_cleanup import get_slot_cleanup_modal_payload
from apps.scheduling.services.slot_cleanup import delete_slot_registration
from apps.scheduling.services.contract_lifecycle import (
    redistribute_contract_slots,
    update_contract_slot_capacities,
)


@login_required(login_url="authentication:staff_login")
def schedule_table(request):
    if not SchedulingPolicy.can_view_schedule_table(request.user):
        messages.error(request, "Ban khong co quyen xem bang lich kham.")
        return redirect("authentication:staff_login")

    context = build_contract_schedule_matrix(actor=request.user)
    context["show_full_company_names"] = SchedulingPolicy.is_manager(request.user)
    return render(request, "booking/staff/schedule_table.html", context)


@login_required(login_url="authentication:staff_login")
@require_POST
def end_schedule(request, config_id):
    try:
        config = ContractScheduleConfig.objects.select_related(
            "quotation", "quotation__created_by"
        ).get(pk=config_id)
    except ContractScheduleConfig.DoesNotExist:
        messages.error(request, "Khong tim thay lich kham.")
        return redirect("scheduling:schedule_table")

    owner_id = getattr(config.quotation, "created_by_id", None) if config.quotation else None
    if not SchedulingPolicy.can_end_schedule(request.user, owner_id):
        messages.error(request, "Ban khong co quyen ket thuc lich kham nay.")
        return redirect("scheduling:schedule_table")

    if not config.is_confirmed:
        messages.error(request, "Chi co the ket thuc lich kham da chot.")
        return redirect("scheduling:schedule_table")

    config.is_ended = True
    config.ended_by = request.user
    config.ended_at = timezone.now()
    config.save(update_fields=["is_ended", "ended_by", "ended_at"])
    messages.success(request, "Da ket thuc lich kham thanh cong.")
    return redirect("scheduling:schedule_table")


@login_required(login_url="authentication:staff_login")
def redistribute_slots(request, contract_id):
    try:
        redistribute_contract_slots(actor=request.user, contract_id=contract_id)
        messages.success(request, "Phan bo lai slot thanh cong.")
    except PermissionError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Loi khi phan bo lai slot: {exc}")

    return redirect("scheduling:schedule_table")


def _config_contract_and_quotation(config):
    contract_profile = getattr(config, "contract", None)
    contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None
    quotation = config.quotation
    return contract_obj, quotation


def _own_slots_qs(contract_obj, quotation):
    if contract_obj:
        return ScheduleSlot.objects.filter(contract=contract_obj, slot_type=SlotType.CONTRACT)
    return ScheduleSlot.objects.filter(quotation=quotation, contract__isnull=True, slot_type=SlotType.CONTRACT)


def _other_totals_by_date_shift(exam_start, exam_end, contract_obj, quotation):
    all_qs = (
        ScheduleSlot.objects
        .filter(date__range=(exam_start, exam_end))
        .values("date", "shift")
        .annotate(total=Sum("capacity"))
    )
    result = defaultdict(int)
    for item in all_qs:
        result[(item["date"].isoformat(), item["shift"])] = item["total"] or 0
    return result


@login_required(login_url="authentication:staff_login")
def get_slot_data(request, config_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        config = ContractScheduleConfig.objects.select_related(
            "quotation", "contract", "contract__contract"
        ).get(pk=config_id)
    except ContractScheduleConfig.DoesNotExist:
        return JsonResponse({"error": "Khong tim thay cau hinh lich."}, status=404)

    contract_obj, quotation = _config_contract_and_quotation(config)
    owner_id = getattr(quotation, "created_by_id", None) if quotation else None
    if not SchedulingPolicy.can_manage_quote_schedule(request.user, owner_id):
        return JsonResponse({"error": "Ban khong co quyen sua slot nay."}, status=403)

    sys = SystemGeneralSetting.get_solo()
    system_am_limit = int(sys.default_am_slot_limit or 0)
    system_pm_limit = int(sys.default_pm_slot_limit or 0)

    exam_start = config.exam_start_date
    exam_end = config.exam_end_date

    own_slots = list(_own_slots_qs(contract_obj, quotation).filter(date__range=(exam_start, exam_end)))
    slot_map = {(s.date.isoformat(), s.shift): s for s in own_slots}

    all_totals = _other_totals_by_date_shift(exam_start, exam_end, contract_obj, quotation)

    from apps.core.models import PublicHoliday
    holiday_dates = set(
        PublicHoliday.objects
        .filter(date__range=(exam_start, exam_end))
        .values_list("date", flat=True)
    )

    weekday_names = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    days_data = []
    current = exam_start
    while current <= exam_end:
        if current.weekday() != 6:
            d_str = current.isoformat()
            is_holiday = current in holiday_dates
            slot_am = slot_map.get((d_str, TimeShift.MORNING))
            slot_pm = slot_map.get((d_str, TimeShift.AFTERNOON))

            am_capacity = slot_am.capacity if slot_am else 0
            pm_capacity = slot_pm.capacity if slot_pm else 0
            am_booked = slot_am.booked_count if slot_am else 0
            pm_booked = slot_pm.booked_count if slot_pm else 0

            total_am = all_totals.get((d_str, TimeShift.MORNING), 0)
            total_pm = all_totals.get((d_str, TimeShift.AFTERNOON), 0)

            am_max = max(0, system_am_limit - (total_am - am_capacity))
            pm_max = max(0, system_pm_limit - (total_pm - pm_capacity))

            am_free = max(0, system_am_limit - total_am)
            pm_free = max(0, system_pm_limit - total_pm)

            days_data.append({
                "date": d_str,
                "date_display": f"{weekday_names[current.weekday()]} {current.strftime('%d/%m')}",
                "is_holiday": is_holiday,
                "am_capacity": am_capacity,
                "pm_capacity": pm_capacity,
                "am_booked": am_booked,
                "pm_booked": pm_booked,
                "am_max": am_max,
                "pm_max": pm_max,
                "am_free": am_free,
                "pm_free": pm_free,
            })
        current += timedelta(days=1)

    current_total = sum(d["am_capacity"] + d["pm_capacity"] for d in days_data)

    return JsonResponse({
        "config_id": config_id,
        "planned_employee_count": config.planned_employee_count,
        "current_total": current_total,
        "system_am_limit": system_am_limit,
        "system_pm_limit": system_pm_limit,
        "days": days_data,
    })


@login_required(login_url="authentication:staff_login")
@require_POST
def update_slot_capacities(request, config_id):
    try:
        body = json.loads(request.body)
        slots_input = body.get("slots", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Du lieu khong hop le."}, status=400)

    try:
        update_contract_slot_capacities(
            actor=request.user,
            config_id=config_id,
            slots_input=slots_input,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except PermissionError as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": exc.message}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"success": True, "message": "Da cap nhat slot thanh cong."})


@login_required(login_url="authentication:staff_login")
def get_slot_cleanup_data(request, config_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = get_slot_cleanup_modal_payload(actor=request.user, config_id=config_id)
    except PermissionError as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": exc.message}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(payload)


@login_required(login_url="authentication:staff_login")
@require_POST
def delete_slot_registration_view(request, appointment_id):
    try:
        result = delete_slot_registration(actor=request.user, appointment_id=appointment_id)
    except PermissionError as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": exc.message}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({
        "success": True,
        "message": f"Da xoa dang ky slot cua {result['patient_name']}.",
        "config_id": result["config_id"],
        "remaining_count": result["remaining_count"],
    })
