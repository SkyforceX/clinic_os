import json
from collections import defaultdict
from datetime import date as date_type
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.booking.models import Appointment
from apps.core.models import SystemGeneralSetting
from apps.his_integration.models import (
    HisDiagnosticImagingItemSync,
    HisPackageServiceSync,
    HisServiceCatalogSync,
)
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType, TimeShift
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_matrix import (
    _appointment_patient,
    _build_config_us_plan,
    _get_company_name_from_config,
    _get_us_service_names,
    _is_ultrasound_service_catalog,
    _is_actor_owned_config,
    _normalize_service_key,
    _display_service_name,
    _patient_gender_code,
    build_contract_schedule_matrix,
)
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


def _format_patient_dob(patient):
    if hasattr(patient, "birth_date_display"):
        return patient.birth_date_display
    dob = getattr(patient, "ngay_sinh", None)
    if dob and hasattr(dob, "strftime"):
        return dob.strftime("%d/%m/%Y")
    return str(dob or "")


def _get_package_ultrasound_code_set(his_package):
    if not his_package:
        return set()

    codes = set()
    rows = (
        HisPackageServiceSync.objects.filter(
            is_active=True,
            is_outside_package=False,
            service_catalog__isnull=False,
        )
        .filter(
            Q(package_sync=his_package)
            | Q(his_package_code=his_package.his_package_code)
            | Q(his_package_code__startswith=f"{his_package.his_package_code}.")
        )
        .select_related("service_catalog")
    )
    for row in rows:
        if _is_ultrasound_service_catalog(getattr(row, "service_catalog", None)):
            code = (row.service_item_code or "").strip()
            if code:
                codes.add(code)
    return codes


def _build_extra_ultrasound_map(*, his_package, patient_ids, target_date):
    if not his_package or not patient_ids:
        return {}

    package_ultrasound_codes = _get_package_ultrasound_code_set(his_package)
    items = list(
        HisDiagnosticImagingItemSync.objects.filter(
            is_active=True,
            imaging_sync__is_active=True,
            imaging_sync__exam_record_sync__package_sync=his_package,
            imaging_sync__exam_record_sync__patient_sync_id__in=patient_ids,
        )
        .filter(
            Q(imaging_sync__exam_record_sync__exam_date=target_date)
            | Q(imaging_sync__exam_date__date=target_date)
        )
        .select_related(
            "imaging_sync",
            "imaging_sync__exam_record_sync",
            "imaging_sync__exam_record_sync__patient_sync",
        )
        .order_by("imaging_sync__exam_record_sync__patient_sync_id", "service_item_code")
    )
    service_codes = {
        (item.service_item_code or "").strip()
        for item in items
        if (item.service_item_code or "").strip()
    }
    catalog_map = {
        catalog.service_item_code: catalog
        for catalog in HisServiceCatalogSync.objects.filter(
            service_item_code__in=service_codes,
            is_active=True,
        )
    }

    extras_by_patient = defaultdict(list)
    seen_by_patient = defaultdict(set)
    for item in items:
        service_code = (item.service_item_code or "").strip()
        if not service_code:
            continue
        catalog = catalog_map.get(service_code)
        if not _is_ultrasound_service_catalog(catalog):
            continue

        is_extra = (item.is_package_service is False) or (service_code not in package_ultrasound_codes)
        if not is_extra:
            continue

        patient = getattr(getattr(item.imaging_sync, "exam_record_sync", None), "patient_sync", None)
        patient_id = getattr(patient, "id", None)
        if not patient_id:
            continue

        service_name = _display_service_name(
            getattr(catalog, "service_item_name", "") or service_code
        )
        service_key = f"extra::{_normalize_service_key(service_name)}::{service_code}"
        if service_key in seen_by_patient[patient_id]:
            continue
        seen_by_patient[patient_id].add(service_key)
        extras_by_patient[patient_id].append({
            "name": service_name,
            "is_extra": True,
            "code": service_code,
        })

    return dict(extras_by_patient)


@login_required(login_url="authentication:staff_login")
def get_us_modal_data(request):
    """AJAX: trả về danh sách BN + siêu âm theo ngày, nhóm theo công ty."""
    if not SchedulingPolicy.can_view_schedule_table(request.user):
        return JsonResponse({"error": "Không có quyền."}, status=403)

    date_str = request.GET.get("date", "")
    try:
        target_date = date_type.fromisoformat(date_str)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Ngày không hợp lệ."}, status=400)

    is_wide_access = SchedulingPolicy.is_executive(request.user) or SchedulingPolicy.is_manager(request.user)

    slot_prefetch = Prefetch(
        "appointments",
        queryset=Appointment.objects.select_related(
            "his_patient_sync", "patient"
        ).order_by("id"),
    )
    configs = list(
        ContractScheduleConfig.objects.filter(
            is_ended=False,
        ).filter(
            Q(
                quotation__schedule_slots__date=target_date,
                quotation__schedule_slots__slot_type=SlotType.CONTRACT,
            )
            |
            Q(
                contract__contract__schedule_slots__date=target_date,
                contract__contract__schedule_slots__slot_type=SlotType.CONTRACT,
            )
        ).select_related(
            "quotation",
            "quotation__company",
            "quotation__created_by",
            "contract",
            "contract__contract",
            "contract__contract__company",
            "registered_by",
            "his_package",
        )
        .prefetch_related(
            Prefetch(
                "quotation__schedule_slots",
                queryset=(
                    ScheduleSlot.objects.filter(
                        date=target_date,
                        slot_type=SlotType.CONTRACT,
                    ).order_by("date", "shift", "id").prefetch_related(slot_prefetch)
                ),
                to_attr="prefetched_schedule_slots",
            ),
            Prefetch(
                "contract__contract__schedule_slots",
                queryset=(
                    ScheduleSlot.objects.filter(
                        date=target_date,
                        slot_type=SlotType.CONTRACT,
                    ).order_by("date", "shift", "id").prefetch_related(slot_prefetch)
                ),
                to_attr="prefetched_schedule_slots",
            ),
            "quotation__company__patients",
            "contract__contract__company__patients",
        )
        .distinct()
    )

    def _build_list(slot, us_lines, extra_services_by_patient):
        patients = []
        if not slot:
            return patients
        for ap in slot.appointments.all():
            patient = _appointment_patient(ap)
            if not patient:
                continue
            gc = _patient_gender_code(patient)
            services = [
                {"name": service_name, "is_extra": False}
                for service_name in _get_us_service_names(us_lines, gc)
            ]
            extras = extra_services_by_patient.get(getattr(patient, "id", None), [])
            services.extend(extras)
            if not services:
                continue
            patients.append({
                "code": getattr(patient, "ma_bn", "") or getattr(patient, "his_patient_code", "") or "",
                "name": getattr(patient, "ho_ten", "") or getattr(patient, "full_name", "") or "",
                "dob": _format_patient_dob(patient),
                "gender": getattr(patient, "gioi_tinh", "") or "",
                "services": services,
            })
        return patients

    companies = []
    total_us = 0
    planned_companies = []
    planned_total_us = 0

    for config in configs:
        us_plan = _build_config_us_plan(config)
        us_lines = us_plan["us_lines"]
        shift_map = {
            shift: slot
            for shift, slot in us_plan["slot_map"].get(target_date, {}).items()
        }
        if not shift_map:
            continue

        masked = not (is_wide_access or _is_actor_owned_config(config, request.user))
        company_name = _get_company_name_from_config(config) or "—"
        if masked:
            company_name = "Lịch khám đã chốt" if config.is_confirmed else "Lịch khám dự kiến"

        patient_ids = set()
        for slot in shift_map.values():
            for ap in slot.appointments.all():
                patient = _appointment_patient(ap)
                patient_id = getattr(patient, "id", None)
                if patient_id:
                    patient_ids.add(patient_id)
        extra_services_by_patient = _build_extra_ultrasound_map(
            his_package=getattr(config, "his_package", None),
            patient_ids=patient_ids,
            target_date=target_date,
        )

        am_patients = _build_list(shift_map.get(TimeShift.MORNING), us_lines, extra_services_by_patient)
        pm_patients = _build_list(shift_map.get(TimeShift.AFTERNOON), us_lines, extra_services_by_patient)
        if am_patients or pm_patients:
            total_us += sum(len(p["services"]) for p in am_patients + pm_patients)
            companies.append({
                "name": company_name,
                "am_patients": am_patients,
                "pm_patients": pm_patients,
            })

        service_counts = us_plan["allocated_daily_service_counts"].get(target_date, {})
        est_us = us_plan["allocated_daily_us"].get(target_date, 0)
        day_cap = sum((slot.capacity or 0) for slot in shift_map.values())
        if day_cap <= 0:
            continue

        planned_total_us += est_us
        planned_companies.append({
            'name': company_name,
            'package_name': getattr(getattr(config, "his_package", None), "package_name", "") or "",
            'allocated_slots': day_cap,
            'us_services': sorted(service_counts.keys()),
            'service_counts': [
                {"name": service_name, "count": count}
                for service_name, count in sorted(
                    service_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
            'estimated_us': est_us,
        })

    planned_companies.sort(key=lambda c: (-c['estimated_us'], -c['allocated_slots'], c['name']))

    return JsonResponse({
        "date": date_str,
        "total": total_us,
        "companies": companies,
        "planned_companies": planned_companies,
        "planned_total_us": planned_total_us,
    })
