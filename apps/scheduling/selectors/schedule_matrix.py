from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Prefetch

from apps.booking.models import Appointment
from apps.core.models import PublicHoliday, SystemGeneralSetting
from apps.his_integration.models import HisExamRecordSync
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType, TimeShift
from apps.scheduling.policies import SchedulingPolicy

User = get_user_model()


def _registered_count(slot):
    if not slot:
        return 0

    prefetched = getattr(slot, "_prefetched_objects_cache", {})
    if "appointments" in prefetched:
        real_count = len(prefetched["appointments"])
    else:
        real_count = slot.appointments.count()

    return max(slot.booked_count or 0, real_count)


def _limit_count(slot):
    if not slot:
        return 0
    return slot.capacity or 0


def _get_company_from_config(config):
    quotation = getattr(config, "quotation", None)
    contract_profile = getattr(config, "contract", None)

    if quotation and getattr(quotation, "company", None):
        return quotation.company

    contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None
    if contract_obj and getattr(contract_obj, "company", None):
        return contract_obj.company

    return None


def _get_company_name_from_config(config):
    company = _get_company_from_config(config)
    if company:
        return company.name

    his_package = getattr(config, "his_package", None)
    if his_package:
        return his_package.company_name or ""

    quotation = getattr(config, "quotation", None)
    if quotation:
        return quotation.company_name or ""

    contract_profile = getattr(config, "contract", None)
    if contract_profile:
        return contract_profile.company_name_snapshot or ""

    return ""


def _get_salesperson_from_config(config):
    quotation = getattr(config, "quotation", None)
    if quotation and getattr(quotation, "created_by", None):
        return quotation.created_by

    contract_profile = getattr(config, "contract", None)
    contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None
    return getattr(contract_obj, "created_by", None)


def _display_user_name(user):
    if not user:
        return ""
    return user.get_full_name() or getattr(user, "username", "") or ""


def _get_schedule_creator_from_config(config):
    creator = getattr(config, "registered_by", None)
    if creator:
        return creator
    return _get_salesperson_from_config(config)


def _get_slots_for_config(config):
    contract_profile = getattr(config, "contract", None)
    contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None
    quotation = getattr(config, "quotation", None)

    merged = []
    seen = set()

    if quotation:
        for slot in getattr(quotation, "prefetched_schedule_slots", []):
            key = (slot.date, slot.shift)
            if key not in seen:
                merged.append(slot)
                seen.add(key)

    if contract_obj:
        for slot in getattr(contract_obj, "prefetched_schedule_slots", []):
            key = (slot.date, slot.shift)
            if key not in seen:
                merged.append(slot)
                seen.add(key)

    return merged


def _get_blood_rows_for_config(config):
    return list(getattr(config, "prefetched_blood_collection_rows", []))


def _get_all_patients_for_config(config):
    his_package = getattr(config, "his_package", None)
    if his_package:
        records = getattr(his_package, "prefetched_exam_records", None)
        if records is None:
            records = (
                his_package.exam_records
                .filter(is_active=True, patient_sync__is_active=True)
                .select_related("patient_sync")
                .order_by("id")
            )
        return [record.patient_sync for record in records if record.patient_sync]

    company = _get_company_from_config(config)
    if company:
        return list(company.patients.all())
    return []


def _appointment_patient(appointment):
    return getattr(appointment, "his_patient_sync", None) or getattr(appointment, "patient", None)


def _patient_identity_key(patient):
    if getattr(patient, "his_patient_code", None):
        return ("his", patient.id)
    return ("legacy", patient.id)


def _patient_payload(patient):
    return {
        "patient_code": patient.ma_bn,
        "name": patient.ho_ten,
        "dob": patient.ngay_sinh.strftime("%d/%m/%Y") if patient.ngay_sinh else "",
    }


def build_contract_schedule_matrix(*, actor, start_of_year=None):
    start_of_year = start_of_year or date.today().replace(month=1, day=1)
    days = [start_of_year + timedelta(days=i) for i in range(365)]

    settings = SystemGeneralSetting.get_solo()
    default_am_limit = int(settings.default_am_slot_limit or 0)
    default_pm_limit = int(settings.default_pm_slot_limit or 0)

    config_qs = (
        ContractScheduleConfig.objects.select_related(
            "quotation",
            "quotation__company",
            "quotation__created_by",
            "contract",
            "contract__quotation",
            "contract__contract",
            "contract__contract__company",
            "contract__contract__created_by",
            "registered_by",
            "his_package",
            "his_package__organization",
        )
        .prefetch_related(
            "quotation__company__patients",
            "contract__contract__company__patients",
            Prefetch(
                "his_package__exam_records",
                queryset=(
                    HisExamRecordSync.objects
                    .filter(is_active=True, patient_sync__is_active=True)
                    .select_related("patient_sync")
                    .order_by("id")
                ),
                to_attr="prefetched_exam_records",
            ),
            Prefetch(
                "blood_collection_rows",
                queryset=(
                    getattr(ContractScheduleConfig, "blood_collection_rows")
                    .rel.related_model.objects.order_by("collection_date", "id")
                ),
                to_attr="prefetched_blood_collection_rows",
            ),
            Prefetch(
                "contract__contract__schedule_slots",
                queryset=(
                    ScheduleSlot.objects.filter(slot_type=SlotType.CONTRACT)
                    .order_by("date", "shift", "id")
                    .prefetch_related(
                        Prefetch(
                            "appointments",
                            queryset=Appointment.objects.select_related(
                                "patient",
                                "his_patient_sync",
                            ).order_by("id"),
                        )
                    )
                ),
                to_attr="prefetched_schedule_slots",
            ),
            Prefetch(
                "quotation__schedule_slots",
                queryset=(
                    ScheduleSlot.objects.filter(slot_type=SlotType.CONTRACT)
                    .order_by("date", "shift", "id")
                    .prefetch_related(
                        Prefetch(
                            "appointments",
                            queryset=Appointment.objects.select_related(
                                "patient",
                                "his_patient_sync",
                            ).order_by("id"),
                        )
                    )
                ),
                to_attr="prefetched_schedule_slots",
            ),
        )
        .order_by("-updated_at", "-id")
    )

    # Lọc bỏ lịch đã kết thúc
    all_configs = [c for c in config_qs if not c.is_ended]

    if SchedulingPolicy.is_executive(actor) or SchedulingPolicy.is_manager(actor):
        # Executives / Managers thấy tất cả với tên đầy đủ, giữ order mặc định (mới nhất trước)
        visible_configs = all_configs
        masked_config_ids = set()
    else:
        # Sales Team: own trước (order -updated_at), sau đó lịch chưa chốt của sale khác (masked)
        own_configs = [
            config
            for config in all_configs
            if getattr(config.quotation, "created_by_id", None) == actor.id
        ]
        own_ids = {config.id for config in own_configs}
        other_unconfirmed = [
            config
            for config in all_configs
            if config.id not in own_ids and not config.is_confirmed
        ]
        visible_configs = own_configs + other_unconfirmed
        masked_config_ids = {config.id for config in other_unconfirmed}

    day_totals = defaultdict(
        lambda: {
            "am": {"registered": 0, "limit": 0},
            "pm": {"registered": 0, "limit": 0},
        }
    )
    daily_blood_totals = {day: {"people": 0, "staff": 0, "locations": 0} for day in days}

    for config in visible_configs:
        slots = _get_slots_for_config(config)
        slot_map = {(slot.date, slot.shift): slot for slot in slots}

        for blood in _get_blood_rows_for_config(config):
            if blood.collection_date in daily_blood_totals:
                daily_blood_totals[blood.collection_date]["people"] += blood.people_count or 0
                daily_blood_totals[blood.collection_date]["staff"] += blood.staff_count or 0
                daily_blood_totals[blood.collection_date]["locations"] += 1

        for day in days:
            slot_am = slot_map.get((day, TimeShift.MORNING))
            slot_pm = slot_map.get((day, TimeShift.AFTERNOON))

            if slot_am:
                day_totals[day]["am"]["registered"] += _registered_count(slot_am)
                day_totals[day]["am"]["limit"] += _limit_count(slot_am)

            if slot_pm:
                day_totals[day]["pm"]["registered"] += _registered_count(slot_pm)
                day_totals[day]["pm"]["limit"] += _limit_count(slot_pm)

    daily_am_totals = []
    daily_pm_totals = []
    for day in days:
        am = day_totals[day]["am"]
        pm = day_totals[day]["pm"]
        daily_am_totals.append(f"Sáng: {am['registered']}/{am['limit']}/{default_am_limit}")
        daily_pm_totals.append(f"Chiều: {pm['registered']}/{pm['limit']}/{default_pm_limit}")

    rows = []
    for config in visible_configs:
        quotation = getattr(config, "quotation", None)
        contract_profile = getattr(config, "contract", None)
        contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None

        is_masked = config.id in masked_config_ids
        company_name = "Lịch khám dự kiến" if is_masked else _get_company_name_from_config(config)
        salesperson = _get_salesperson_from_config(config)
        schedule_creator = getattr(config, "registered_by", None)
        if not schedule_creator:
            schedule_creator = _get_schedule_creator_from_config(config)
        creator_name = _display_user_name(schedule_creator)
        if is_masked:
            company_name = creator_name or "Lich kham du kien"
        elif not company_name:
            company_name = creator_name or company_name

        blood_collection_list = _get_blood_rows_for_config(config)
        blood_dates = [bc.collection_date.strftime("%Y-%m-%d") for bc in blood_collection_list]

        slots = _get_slots_for_config(config)
        slot_map = {(slot.date, slot.shift): slot for slot in slots}

        all_patients = _get_all_patients_for_config(config)
        registered_patient_ids = {
            _patient_identity_key(patient)
            for slot in slots
            for ap in slot.appointments.all()
            for patient in [_appointment_patient(ap)]
            if patient
        }

        # ── Kế hoạch triển khai ───────────────────────────────────────────────
        impl_plan = None
        impl_plan_id = None
        impl_plan_is_published = False
        if contract_obj:
            try:
                impl_plan = getattr(contract_obj, "implementation_plan", None)
                if impl_plan is None:
                    # Thử lấy từ DB (trường hợp chưa prefetch)
                    from apps.contract.models import ImplementationPlan
                    impl_plan = ImplementationPlan.objects.filter(
                        contract=contract_obj
                    ).first()
            except Exception:
                impl_plan = None
            if impl_plan:
                impl_plan_id = impl_plan.pk
                impl_plan_is_published = getattr(impl_plan, "is_published", False)

        can_create_impl_plan = (
            bool(contract_obj)
            and SchedulingPolicy.can_manage_quote_schedule(
                actor,
                getattr(contract_obj, "created_by_id", None),
            )
        )

        owner_id = getattr(quotation, "created_by_id", None) if quotation else None
        can_end = (
            config.is_confirmed
            and not config.is_ended
            and SchedulingPolicy.can_end_schedule(actor, owner_id)
        )

        row = {
            "planned_employee_count": config.planned_employee_count,
            "can_edit_slots": (
                not is_masked
                and SchedulingPolicy.can_manage_quote_schedule(actor, owner_id)
            ),
            "schedule_config_id": config.id,
            "contract_id": contract_obj.id if contract_obj else None,
            "contract_number": getattr(contract_obj, "contract_number", "") if contract_obj else "",
            "company_name": company_name,
            "salesperson_name": _display_user_name(salesperson),
            "salesperson_id": salesperson.id if salesperson else "",
            "schedule_creator_name": creator_name,
            "can_delete_schedule": (
                (not contract_profile)
                and SchedulingPolicy.can_manage_quote_schedule(
                    actor,
                    getattr(quotation, "created_by_id", None),
                )
            ),
            "can_end_schedule": can_end,
            "is_confirmed": config.is_confirmed,
            "is_masked_company": is_masked,
            "can_create_impl_plan": can_create_impl_plan,
            "impl_plan_id": impl_plan_id,
            "impl_plan_is_published": impl_plan_is_published,
            "blood_dates": blood_dates,
            "unregistered_patients": [
                _patient_payload(patient)
                for patient in all_patients
                if _patient_identity_key(patient) not in registered_patient_ids
            ],
            "schedule": [],
        }

        exam_start = getattr(config, "exam_start_date", None)
        exam_end = getattr(config, "exam_end_date", None)

        for day in days:
            info = next((bc for bc in blood_collection_list if bc.collection_date == day), None)
            slot_am = slot_map.get((day, TimeShift.MORNING))
            slot_pm = slot_map.get((day, TimeShift.AFTERNOON))

            cell = {
                "date": day.strftime("%Y-%m-%d"),
                "am": "",
                "pm": "",
                "is_full_am": False,
                "is_full_pm": False,
                "in_range": bool(exam_start and exam_end and exam_start <= day <= exam_end),
                "is_blood": day.strftime("%Y-%m-%d") in blood_dates,
                "is_sunday": day.weekday() == 6,
                "collection_date": info.collection_date.strftime("%d-%m-%Y") if info else None,
                "location": info.location if info else None,
                "blood_people_count": info.people_count if info else None,
                "blood_staff_count": info.staff_count if info else None,
                "am_patients": [],
                "pm_patients": [],
            }

            if slot_am:
                reg_am = _registered_count(slot_am)
                lim_am = _limit_count(slot_am)
                cell["am"] = f"{reg_am}/{lim_am}"
                cell["is_full_am"] = lim_am > 0 and reg_am >= lim_am
                cell["am_patients"] = [
                    _patient_payload(patient)
                    for ap in slot_am.appointments.all()
                    for patient in [_appointment_patient(ap)]
                    if patient
                ]

            if slot_pm:
                reg_pm = _registered_count(slot_pm)
                lim_pm = _limit_count(slot_pm)
                cell["pm"] = f"{reg_pm}/{lim_pm}"
                cell["is_full_pm"] = lim_pm > 0 and reg_pm >= lim_pm
                cell["pm_patients"] = [
                    _patient_payload(patient)
                    for ap in slot_pm.appointments.all()
                    for patient in [_appointment_patient(ap)]
                    if patient
                ]

            row["schedule"].append(cell)

        rows.append(row)

    sale_team_users = User.objects.filter(groups__name="Sales Team").distinct()
    blood_totals_per_day = [daily_blood_totals[day] for day in days]
    sunday_indexes = [index for index, day in enumerate(days) if day.weekday() == 6]

    holiday_date_set = set(PublicHoliday.objects.values_list("date", flat=True))
    holiday_indexes = {index for index, day in enumerate(days) if day in holiday_date_set}

    return {
        "days": days,
        "schedule_rows": rows,
        "daily_am_totals": daily_am_totals,
        "daily_pm_totals": daily_pm_totals,
        "blood_totals_per_day": blood_totals_per_day,
        "sunday_indexes": sunday_indexes,
        "holiday_indexes": holiday_indexes,
        "sale_team_users": sale_team_users,
        "show_staff_filter": SchedulingPolicy.is_manager(actor),
        "current_staff_id": str(actor.id) if getattr(actor, "id", None) else "",
        "system_am_limit": default_am_limit,
        "system_pm_limit": default_pm_limit,
    }

