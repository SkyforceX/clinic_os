from collections import Counter, defaultdict
from datetime import date, timedelta
import re
from types import SimpleNamespace
import unicodedata

from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q

from apps.booking.models import Appointment
from apps.core.models import PublicHoliday, SystemGeneralSetting
from apps.his_integration.models import HisExamRecordSync, HisPackageServiceSync
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


def _is_actor_owned_config(config, actor):
    if not actor:
        return False

    salesperson = _get_salesperson_from_config(config)
    if getattr(salesperson, "id", None) == actor.id:
        return True

    creator = getattr(config, "registered_by", None)
    return getattr(creator, "id", None) == actor.id


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


def _patient_gender_code(patient):
    """Return '0' for male, '1' for female, '' for unknown."""
    if patient is None:
        return ""
    gc = getattr(patient, "gender_code", None)
    if gc is not None:
        return (gc or "").strip()
    gt = (getattr(patient, "gioi_tinh", "") or "").strip().lower()
    if "nam" in gt or gt == "m":
        return "0"
    if "nữ" in gt or "nu" in gt or gt == "f":
        return "1"
    return ""


def _strip_accents(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_service_key(name):
    text = _strip_accents(name).lower().strip()
    text = re.sub(r"\s*[-/]\s*(nam|nu|nữ)\s*$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _display_service_name(name):
    text = str(name or "").strip()
    text = re.sub(r"\s*[-/]\s*(Nam|Nữ|Nu)\s*$", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_service_names(names):
    deduped = []
    seen = set()
    for name in names:
        normalized = _normalize_service_key(name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(_display_service_name(name))
    return deduped


def _is_ultrasound_service_catalog(service_catalog):
    if not service_catalog:
        return False

    haystacks = [
        getattr(service_catalog, "service_item_name", ""),
        getattr(service_catalog, "service_item_name_order", ""),
        getattr(service_catalog, "service_group_code", ""),
        getattr(service_catalog, "service_sub_group_code", ""),
        getattr(service_catalog, "report_group_code", ""),
        getattr(service_catalog, "common_group_code", ""),
    ]
    normalized = " | ".join(_strip_accents(value).lower() for value in haystacks if value)
    if not normalized:
        return False

    ultrasound_keywords = [
        "sieu am",
        "sieuam",
        "ultrasound",
    ]
    if any(keyword in normalized for keyword in ultrasound_keywords):
        return True

    code_tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", normalized)
        if token
    }
    return "sa" in code_tokens and ("cdha" in code_tokens or "cls" in code_tokens)


def _get_us_service_names(us_lines, gender_code):
    if not us_lines:
        return []

    g = gender_code
    result = []
    for line in us_lines:
        if not getattr(line, "item_name", ""):
            continue
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
    return _dedupe_service_names(result)


def _count_us_services(us_lines, gender_code):
    """Count applicable ultrasound services for a patient based on gender."""
    return len(_get_us_service_names(us_lines, gender_code))


def _count_us_services_for_group(us_lines, group_key):
    """Count applicable ultrasound services for a quotation gender group."""
    if not us_lines:
        return 0

    names = []
    for line in us_lines:
        if group_key == "male":
            if line.for_male and line.checked_male:
                names.append(line.item_name)
        elif group_key == "female_single":
            if line.for_female_single and line.checked_female_single:
                names.append(line.item_name)
        elif group_key == "female_family":
            if line.for_female_family and line.checked_female_family:
                names.append(line.item_name)

    return len(_dedupe_service_names(names))


def _build_allocated_us_totals(slot_map, us_total):
    """
    Distribute estimated ultrasound workload by allocated slot capacity per day.

    Uses largest-remainder rounding so the final daily sum matches `us_total`.
    """
    daily_capacities = []
    total_capacity = 0

    for day, shifts in slot_map.items():
        day_capacity = sum(_limit_count(slot) for slot in shifts.values())
        if day_capacity <= 0:
            continue
        daily_capacities.append((day, day_capacity))
        total_capacity += day_capacity

    if us_total <= 0 or total_capacity <= 0:
        return {}

    allocated = {}
    remainders = []
    assigned_total = 0

    for day, day_capacity in daily_capacities:
        raw_value = (us_total * day_capacity) / total_capacity
        base_value = int(raw_value)
        allocated[day] = base_value
        assigned_total += base_value
        remainders.append((raw_value - base_value, day))

    remaining = us_total - assigned_total
    for _, day in sorted(remainders, key=lambda item: (-item[0], item[1])):
        if remaining <= 0:
            break
        allocated[day] += 1
        remaining -= 1

    return allocated


def _get_us_lines_for_config(config):
    his_package = getattr(config, "his_package", None)
    if not his_package:
        return []

    service_names = []
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
        service_catalog = getattr(row, "service_catalog", None)
        if not _is_ultrasound_service_catalog(service_catalog):
            continue
        service_name = getattr(service_catalog, "service_item_name", "") or ""
        if service_name:
            service_names.append(service_name)

    unique_names = _dedupe_service_names(service_names)
    return [
        SimpleNamespace(
            item_name=name,
            for_male=True,
            for_female_single=True,
            for_female_family=True,
            checked_male=True,
            checked_female_single=True,
            checked_female_family=True,
        )
        for name in unique_names
    ]


def _build_slot_map_by_day(slots):
    slot_map = defaultdict(dict)
    for slot in slots:
        slot_map[slot.date][slot.shift] = slot
    return slot_map


def _build_allocated_us_service_counts(slot_map, service_counts):
    allocated = defaultdict(dict)
    for service_name, total_count in service_counts.items():
        if total_count <= 0:
            continue
        for day, day_count in _build_allocated_us_totals(slot_map, total_count).items():
            if day_count > 0:
                allocated[day][service_name] = day_count
    return dict(allocated)


def _get_max_us_service_names(us_lines):
    names = []
    for line in us_lines:
        if not getattr(line, "item_name", ""):
            continue
        if (
            (line.for_male and line.checked_male)
            or (line.for_female_single and line.checked_female_single)
            or (line.for_female_family and line.checked_female_family)
        ):
            names.append(line.item_name)

    return _dedupe_service_names(names)


def _build_config_us_plan(config):
    us_lines = _get_us_lines_for_config(config)
    slots = _get_slots_for_config(config)
    slot_map = _build_slot_map_by_day(slots)
    max_us_service_names = _get_max_us_service_names(us_lines)
    max_us_per_person = len(max_us_service_names)

    service_counts = Counter()
    total_us = 0
    for patient in _get_all_patients_for_config(config):
        service_names = _get_us_service_names(us_lines, _patient_gender_code(patient))
        if not service_names:
            continue
        total_us += len(service_names)
        service_counts.update(service_names)

    allocated_daily_us = {}
    allocated_daily_service_counts = {}
    for day, shifts in slot_map.items():
        day_capacity = sum(_limit_count(slot) for slot in shifts.values())
        if day_capacity <= 0 or max_us_per_person <= 0:
            continue
        allocated_daily_us[day] = day_capacity * max_us_per_person
        allocated_daily_service_counts[day] = {
            service_name: day_capacity for service_name in max_us_service_names
        }

    return {
        "us_lines": us_lines,
        "slot_map": slot_map,
        "total_us": total_us,
        "service_counts": dict(service_counts),
        "max_us_per_person": max_us_per_person,
        "max_us_service_names": max_us_service_names,
        "allocated_daily_us": allocated_daily_us,
        "allocated_daily_service_counts": allocated_daily_service_counts,
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

    has_wide_access = (
        SchedulingPolicy.is_executive(actor)
        or SchedulingPolicy.is_manager(actor)
        or SchedulingPolicy.can_cleanup_slot_registrations(actor)
    )

    if has_wide_access:
        # Executives / Managers thấy tất cả với tên đầy đủ, giữ order mặc định (mới nhất trước)
        visible_configs = all_configs
        masked_config_ids = set()
    else:
        # Sales Team: own trước (order -updated_at), sau đó lịch chưa chốt của sale khác (masked)
        own_configs = [
            config
            for config in all_configs
            if _is_actor_owned_config(config, actor)
        ]
        own_ids = {config.id for config in own_configs}
        other_configs = [
            config
            for config in all_configs
            if config.id not in own_ids
        ]
        visible_configs = own_configs + other_configs
        masked_config_ids = {config.id for config in other_configs}

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

    # ─── Tổng siêu âm mỗi ngày ───────────────────────────────────────────────
    daily_us_counts = defaultdict(int)
    daily_us_allocated_counts = defaultdict(int)
    daily_us_registered_company_counts = defaultdict(int)
    daily_us_allocated_company_counts = defaultdict(int)
    for config in visible_configs:
        us_plan = _build_config_us_plan(config)
        us_lines = us_plan["us_lines"]
        slot_map_us = us_plan["slot_map"]
        for day, shifts in slot_map_us.items():
            day_capacity = sum(_limit_count(slot) for slot in shifts.values())
            if day_capacity > 0:
                daily_us_allocated_company_counts[day] += 1

        if not us_lines:
            continue

        has_registered_by_day = set()
        for day in days:
            for shift in (TimeShift.MORNING, TimeShift.AFTERNOON):
                slot = slot_map_us.get(day, {}).get(shift)
                if not slot:
                    continue
                for ap in slot.appointments.all():
                    patient = _appointment_patient(ap)
                    if not patient:
                        continue
                    registered_us = _count_us_services(us_lines, _patient_gender_code(patient))
                    if registered_us > 0:
                        daily_us_counts[day] += registered_us
                        has_registered_by_day.add(day)

        for day, allocated_us in us_plan["allocated_daily_us"].items():
            if allocated_us > 0:
                daily_us_allocated_counts[day] += allocated_us

        for day in has_registered_by_day:
            daily_us_registered_company_counts[day] += 1

    daily_us_data = [
        {
            "date": day.strftime("%Y-%m-%d"),
            "total": daily_us_counts.get(day, 0),
            "registered_total": daily_us_counts.get(day, 0),
            "allocated_total": daily_us_allocated_counts.get(day, 0),
            "registered_company_count": daily_us_registered_company_counts.get(day, 0),
            "allocated_company_count": daily_us_allocated_company_counts.get(day, 0),
        }
        for day in days
    ]

    rows = []
    for config in visible_configs:
        quotation = getattr(config, "quotation", None)
        contract_profile = getattr(config, "contract", None)
        contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None

        is_masked = config.id in masked_config_ids
        company_name = "Lịch khám dự kiến" if is_masked else _get_company_name_from_config(config)
        if is_masked:
            company_name = (
                "Lịch khám đã chốt" if config.is_confirmed else "Lịch khám dự kiến"
            )
        salesperson = _get_salesperson_from_config(config)
        schedule_creator = getattr(config, "registered_by", None)
        if not schedule_creator:
            schedule_creator = _get_schedule_creator_from_config(config)
        creator_name = _display_user_name(schedule_creator)
        if not is_masked and not company_name:
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
        can_confirm = (
            (not is_masked)
            and (not config.is_confirmed)
            and (not config.is_ended)
            and SchedulingPolicy.can_manage_quote_schedule(actor, owner_id)
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
                (not config.is_confirmed)
                and
                (not contract_profile)
                and SchedulingPolicy.can_manage_quote_schedule(
                    actor,
                    getattr(quotation, "created_by_id", None),
                )
            ),
            "can_confirm_schedule": can_confirm,
            "can_end_schedule": can_end,
            "can_cleanup_slot_registrations": SchedulingPolicy.can_cleanup_slot_registrations(actor),
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
        "daily_us_data": daily_us_data,
        "sunday_indexes": sunday_indexes,
        "holiday_indexes": holiday_indexes,
        "sale_team_users": sale_team_users,
        "show_staff_filter": SchedulingPolicy.is_manager(actor),
        "current_staff_id": str(actor.id) if getattr(actor, "id", None) else "",
        "system_am_limit": default_am_limit,
        "system_pm_limit": default_pm_limit,
        "can_cleanup_slot_registrations": SchedulingPolicy.can_cleanup_slot_registrations(actor),
    }
