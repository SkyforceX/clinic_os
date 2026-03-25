import calendar
from datetime import date

from apps.contract.models import Contract
from apps.scheduling.models import Appointment, ScheduleSlot, TimeShift


def list_schedule_contracts_for_actor(*, user):
    qs = (
        Contract.objects.select_related("company", "created_by")
        .filter(is_finished=False)
        .order_by("-created_at")
    )

    if user.is_superuser or user.groups.filter(name__in=["Manager", "Managers"]).exists():
        return qs

    return qs.filter(created_by=user)


def get_contract_for_actor(*, user, contract_id):
    return list_schedule_contracts_for_actor(user=user).filter(id=contract_id).first()


def get_latest_contract_for_patient(patient):
    if not getattr(patient, "company_id", None):
        return None

    return (
        Contract.objects.filter(company_id=patient.company_id)
        .order_by("-start_date", "-id")
        .first()
    )


def get_month_list(start_date, end_date):
    if not start_date or not end_date:
        return []

    months = []
    current = date(start_date.year, start_date.month, 1)
    end = date(end_date.year, end_date.month, 1)

    while current <= end:
        months.append((current.year, current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return months


def build_patient_registration_calendar(*, contract):
    schedules = ScheduleSlot.objects.filter(contract=contract).order_by("date", "shift")
    slot_map = {(slot.date, slot.shift): slot for slot in schedules}

    month_list = get_month_list(contract.start_date, contract.end_date)
    months_data = []
    slot_status = {}

    for year_value, month_value in month_list:
        num_days = calendar.monthrange(year_value, month_value)[1]
        days_in_month = [date(year_value, month_value, day) for day in range(1, num_days + 1)]
        schedule_data = {}

        for day in days_in_month:
            in_contract_range = contract.start_date <= day <= contract.end_date
            day_data = {}
            disabled_all = True

            for shift_label, shift_value in [
                ("MORNING", TimeShift.MORNING),
                ("AFTERNOON", TimeShift.AFTERNOON),
            ]:
                slot = slot_map.get((day, shift_value))

                if slot:
                    if shift_value == TimeShift.MORNING:
                        registered = slot.registered_am
                        max_slot = slot.limit_am
                    else:
                        registered = slot.registered_pm
                        max_slot = slot.limit_pm
                else:
                    registered = 0
                    max_slot = 0

                remaining = max(0, max_slot - registered)

                if in_contract_range and remaining > 0:
                    disabled_all = False

                day_data[shift_label] = {
                    "remaining": remaining if in_contract_range else 0,
                    "max": max_slot if in_contract_range else 0,
                    "disabled": (not in_contract_range) or remaining == 0,
                    "schedule_id": slot.id if slot else None,
                }

            day_data["disabled_all"] = (not in_contract_range) or disabled_all
            schedule_data[str(day)] = day_data
            slot_status[str(day)] = {
                "am": day_data["MORNING"]["remaining"],
                "pm": day_data["AFTERNOON"]["remaining"],
            }

        weeks = list(calendar.Calendar(firstweekday=0).monthdatescalendar(year_value, month_value))
        months_data.append(
            {
                "year": year_value,
                "month": month_value,
                "weeks": weeks,
                "schedule_data": schedule_data,
            }
        )

    return {
        "months_data": months_data,
        "slot_status": slot_status,
    }


def get_existing_appointment_for_patient_in_contract(*, patient, contract):
    return (
        Appointment.objects.select_related("schedule")
        .filter(
            patient=patient,
            schedule__contract=contract,
        )
        .first()
    )