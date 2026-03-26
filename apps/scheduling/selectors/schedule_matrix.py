from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Prefetch

from apps.booking.models import Appointment
from apps.contract.models import CLOSED_STATUSES, BloodCollectionSchedule, Contract
from apps.scheduling.models import ScheduleSlot
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


def build_contract_schedule_matrix(*, actor, start_of_year=None):
    start_of_year = start_of_year or date.today().replace(month=1, day=1)
    days = [start_of_year + timedelta(days=i) for i in range(365)]

    contract_qs = (
        Contract.objects
        .exclude(status__in=CLOSED_STATUSES)
        .select_related("company", "created_by")
        .prefetch_related(
            "company__patients",
            Prefetch(
                "blood_collection_schedules",
                queryset=BloodCollectionSchedule.objects.order_by("collection_date", "id"),
            ),
            Prefetch(
                "schedule_slots",
                queryset=(
                    ScheduleSlot.objects.order_by("date", "shift", "id").prefetch_related(
                        Prefetch(
                            "appointments",
                            queryset=Appointment.objects.select_related("patient").order_by("id"),
                        )
                    )
                ),
            ),
        )
        .order_by("-created_at")
    )

    all_contracts = list(contract_qs)

    if SchedulingPolicy.is_manager(actor):
        visible_contracts = all_contracts
    else:
        visible_contracts = [contract for contract in all_contracts if contract.created_by_id == actor.id]

    day_totals = defaultdict(
        lambda: {
            "am": {"registered": 0, "limit": 0},
            "pm": {"registered": 0, "limit": 0},
        }
    )
    daily_blood_totals = {day: {"people": 0, "staff": 0, "locations": 0} for day in days}

    for contract in all_contracts:
        slot_map = {(slot.date, slot.shift): slot for slot in contract.schedule_slots.all()}

        for blood in contract.blood_collection_schedules.all():
            if blood.collection_date in daily_blood_totals:
                daily_blood_totals[blood.collection_date]["people"] += blood.people_count or 0
                daily_blood_totals[blood.collection_date]["staff"] += blood.staff_count or 0
                daily_blood_totals[blood.collection_date]["locations"] += 1

        for day in days:
            slot_am = slot_map.get((day, "AM"))
            slot_pm = slot_map.get((day, "PM"))

            if slot_am:
                day_totals[day]["am"]["registered"] += _registered_count(slot_am)
                day_totals[day]["am"]["limit"] += _limit_count(slot_am)

            if slot_pm:
                day_totals[day]["pm"]["registered"] += _registered_count(slot_pm)
                day_totals[day]["pm"]["limit"] += _limit_count(slot_pm)

    default_am_limit = 100
    default_pm_limit = 100

    daily_am_totals = []
    daily_pm_totals = []
    for day in days:
        am = day_totals[day]["am"]
        pm = day_totals[day]["pm"]
        daily_am_totals.append(f"Sáng: {am['registered']}/{am['limit']}/{default_am_limit}")
        daily_pm_totals.append(f"Chiều: {pm['registered']}/{pm['limit']}/{default_pm_limit}")

    rows = []
    for contract in visible_contracts:
        blood_collection_list = list(contract.blood_collection_schedules.all())
        blood_dates = [bc.collection_date.strftime("%Y-%m-%d") for bc in blood_collection_list]
        slot_map = {(slot.date, slot.shift): slot for slot in contract.schedule_slots.all()}

        all_patients = list(contract.company.patients.all())
        registered_patient_ids = {
            ap.patient_id
            for schedule in contract.schedule_slots.all()
            for ap in schedule.appointments.all()
        }

        row = {
            "contract_id": contract.id,
            "contract_number": contract.contract_number,
            "company_name": contract.company.name,
            "salesperson_name": contract.created_by.get_full_name() if contract.created_by else "",
            "salesperson_id": contract.created_by_id or "",
            "blood_dates": blood_dates,
            "unregistered_patients": [
                {
                    "patient_code": patient.ma_bn,
                    "name": patient.ho_ten,
                    "dob": patient.ngay_sinh.strftime("%d/%m/%Y") if patient.ngay_sinh else "",
                }
                for patient in all_patients
                if patient.id not in registered_patient_ids
            ],
            "schedule": [],
        }

        for day in days:
            info = next((bc for bc in blood_collection_list if bc.collection_date == day), None)
            slot_am = slot_map.get((day, "AM"))
            slot_pm = slot_map.get((day, "PM"))

            cell = {
                "date": day.strftime("%Y-%m-%d"),
                "am": "",
                "pm": "",
                "is_full_am": False,
                "is_full_pm": False,
                "in_range": bool(contract.start_date and contract.end_date and contract.start_date <= day <= contract.end_date),
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
                    {
                        "patient_code": ap.patient.ma_bn,
                        "name": ap.patient.ho_ten,
                        "dob": ap.patient.ngay_sinh.strftime("%d/%m/%Y") if ap.patient.ngay_sinh else "",
                    }
                    for ap in slot_am.appointments.all()
                ]

            if slot_pm:
                reg_pm = _registered_count(slot_pm)
                lim_pm = _limit_count(slot_pm)
                cell["pm"] = f"{reg_pm}/{lim_pm}"
                cell["is_full_pm"] = lim_pm > 0 and reg_pm >= lim_pm
                cell["pm_patients"] = [
                    {
                        "patient_code": ap.patient.ma_bn,
                        "name": ap.patient.ho_ten,
                        "dob": ap.patient.ngay_sinh.strftime("%d/%m/%Y") if ap.patient.ngay_sinh else "",
                    }
                    for ap in slot_pm.appointments.all()
                ]

            row["schedule"].append(cell)

        rows.append(row)

    sale_team_users = User.objects.filter(groups__name="Sales Team").distinct()
    blood_totals_per_day = [daily_blood_totals[day] for day in days]
    sunday_indexes = [index for index, day in enumerate(days) if day.weekday() == 6]

    return {
        "days": days,
        "schedule_rows": rows,
        "daily_am_totals": daily_am_totals,
        "daily_pm_totals": daily_pm_totals,
        "blood_totals_per_day": blood_totals_per_day,
        "sunday_indexes": sunday_indexes,
        "sale_team_users": sale_team_users,
    }