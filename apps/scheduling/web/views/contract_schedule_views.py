import json
from collections import defaultdict
from datetime import date as date_type
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.booking.models import Appointment
from apps.contract.models import QuotationLine
from apps.his_integration.models import HisPackageServiceSync
from apps.core.models import SystemGeneralSetting
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType, TimeShift
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_matrix import (
    _appointment_patient,
    _count_us_services,
    _patient_gender_code,
    build_contract_schedule_matrix,
)
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


def _get_us_service_names(us_lines, gender_code):
    if not us_lines:
        return []
    g = gender_code
    result = []
    for line in us_lines:
        if g == "0":  # male
            if line.for_male and line.checked_male:
                result.append(line.item_name)
        elif g == "1":  # female
            if (line.for_female_single and line.checked_female_single) or (
                line.for_female_family and line.checked_female_family
            ):
                result.append(line.item_name)
        else:  # unknown
            if (
                (line.for_male and line.checked_male)
                or (line.for_female_single and line.checked_female_single)
                or (line.for_female_family and line.checked_female_family)
            ):
                result.append(line.item_name)
    return result


def _format_patient_dob(patient):
    if hasattr(patient, "birth_date_display"):
        return patient.birth_date_display
    dob = getattr(patient, "ngay_sinh", None)
    if dob and hasattr(dob, "strftime"):
        return dob.strftime("%d/%m/%Y")
    return str(dob or "")


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

    slots = list(
        ScheduleSlot.objects.filter(date=target_date, slot_type=SlotType.CONTRACT)
        .select_related("quotation__company", "quotation__created_by")
        .prefetch_related(
            Prefetch(
                "appointments",
                queryset=Appointment.objects.select_related(
                    "his_patient_sync", "patient"
                ).order_by("id"),
            )
        )
    )

    q_ids = {s.quotation_id for s in slots if s.quotation_id}
    us_lines_map = defaultdict(list)
    for line in QuotationLine.objects.filter(
        quotation_id__in=q_ids, group_name__icontains="siêu âm"
    ):
        us_lines_map[line.quotation_id].append(line)

    # Nhóm slot theo quotation_id + shift
    slots_by_q = defaultdict(dict)
    company_name_by_q = {}
    for slot in slots:
        q_id = slot.quotation_id
        if not q_id:
            continue
        slots_by_q[q_id][slot.shift] = slot
        if q_id not in company_name_by_q:
            q = slot.quotation
            if is_wide_access:
                company_name_by_q[q_id] = (
                    (q.company.name if q and q.company else None) or (q.company_name if q else "") or "—"
                )
            else:
                owner_id = getattr(q, "created_by_id", None) if q else None
                if owner_id == request.user.id:
                    company_name_by_q[q_id] = (
                        (q.company.name if q and q.company else None) or (q.company_name if q else "") or "—"
                    )
                else:
                    company_name_by_q[q_id] = "Lịch khám dự kiến"

    def _build_list(slot, us_lines):
        patients = []
        if not slot:
            return patients
        for ap in slot.appointments.all():
            patient = _appointment_patient(ap)
            if not patient:
                continue
            gc = _patient_gender_code(patient)
            services = _get_us_service_names(us_lines, gc)
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
    for q_id in slots_by_q:
        us_lines = us_lines_map.get(q_id, [])
        shift_map = slots_by_q[q_id]
        am_patients = _build_list(shift_map.get(TimeShift.MORNING), us_lines)
        pm_patients = _build_list(shift_map.get(TimeShift.AFTERNOON), us_lines)
        if am_patients or pm_patients:
            total_us += sum(len(p["services"]) for p in am_patients + pm_patients)
            companies.append({
                "name": company_name_by_q.get(q_id, "—"),
                "am_patients": am_patients,
                "pm_patients": pm_patients,
            })

    # ── Planned: US services per company from HIS packages ──────────────────
    configs = list(
        ContractScheduleConfig.objects.filter(
            quotation_id__in=q_ids,
            is_ended=False,
        ).select_related('his_package')
    )
    config_by_q = {c.quotation_id: c for c in configs}

    pkg_codes = [c.his_package.his_package_code for c in configs if c.his_package]
    us_svc_by_pkg = defaultdict(list)
    if pkg_codes:
        for ps in HisPackageServiceSync.objects.filter(
            his_package_code__in=pkg_codes,
            is_active=True,
            is_outside_package=False,
            service_catalog__isnull=False,
            service_catalog__service_item_name__icontains='siêu âm',
        ).select_related('service_catalog'):
            us_svc_by_pkg[ps.his_package_code].append(ps.service_catalog.service_item_name)

    planned_companies = []
    planned_total_us = 0
    for q_id in slots_by_q:
        shift_map = slots_by_q[q_id]
        day_cap = sum((s.capacity or 0) for s in shift_map.values())
        config = config_by_q.get(q_id)
        pkg = getattr(config, 'his_package', None) if config else None

        if pkg:
            svc_names = list(us_svc_by_pkg.get(pkg.his_package_code, []))
            pkg_name = pkg.package_name or ''
        else:
            svc_names = list({ln.item_name for ln in us_lines_map.get(q_id, []) if ln.item_name})
            pkg_name = ''

        est_us = day_cap * len(svc_names)
        planned_total_us += est_us
        planned_companies.append({
            'name': company_name_by_q.get(q_id, '—'),
            'package_name': pkg_name,
            'allocated_slots': day_cap,
            'us_services': svc_names,
            'estimated_us': est_us,
        })

    planned_companies.sort(key=lambda c: (-len(c['us_services']), -c['allocated_slots']))

    return JsonResponse({
        "date": date_str,
        "total": total_us,
        "companies": companies,
        "planned_companies": planned_companies,
        "planned_total_us": planned_total_us,
    })
