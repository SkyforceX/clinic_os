import calendar
from datetime import date

from apps.booking.models import Appointment
from apps.contract.models import CLOSED_STATUSES, Contract
from apps.his_integration.selectors import get_latest_schedule_config_for_his_patient
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType, TimeShift


def list_schedule_contracts_for_actor(*, user):
    qs = (
        Contract.objects
        .select_related("company", "created_by")
        .exclude(status__in=CLOSED_STATUSES)
        .order_by("-created_at")
    )

    if user.is_superuser or user.groups.filter(name__in=["Managers", "Manager"]).exists():
        return qs

    return qs.filter(created_by=user)


def get_contract_for_actor(*, user, contract_id):
    return list_schedule_contracts_for_actor(user=user).filter(id=contract_id).first()


def get_latest_contract_for_patient(patient):
    company_id = getattr(patient, "company_id", None)
    if not company_id:
        return None

    return (
        Contract.objects
        .filter(company_id=company_id)
        .exclude(status__in=CLOSED_STATUSES)
        .order_by("-start_date", "-id")
        .first()
    )


def _schedule_config_actual_contract(config):
    profile = getattr(config, "contract", None)
    return getattr(profile, "contract", None) if profile else None


def get_latest_schedule_config_for_patient(patient):
    patient_code = getattr(patient, "ma_bn", "")
    his_config = get_latest_schedule_config_for_his_patient(patient_code=patient_code)
    if his_config:
        return his_config

    company_id = getattr(patient, "company_id", None)
    if not company_id:
        return None

    return (
        ContractScheduleConfig.objects.select_related(
            "quotation",
            "quotation__company",
            "contract",
            "contract__contract",
            "his_package",
        )
        .filter(quotation__company_id=company_id)
        .order_by("-exam_start_date", "-id")
        .first()
    )


def _appointment_patient_filter(patient):
    if getattr(patient, "his_patient_code", None):
        return {"his_patient_sync": patient}
    return {"patient": patient}


def get_existing_appointment_for_patient_in_contract(*, patient, contract):
    return (
        Appointment.objects
        .select_related("schedule_slot")
        .filter(
            **_appointment_patient_filter(patient),
            schedule_slot__contract=contract,
        )
        .first()
    )


def get_existing_appointment_for_patient_in_schedule_config(*, patient, schedule_config):
    actual_contract = _schedule_config_actual_contract(schedule_config)
    if actual_contract:
        return get_existing_appointment_for_patient_in_contract(
            patient=patient,
            contract=actual_contract,
        )

    return (
        Appointment.objects
        .select_related("schedule_slot")
        .filter(
            **_appointment_patient_filter(patient),
            schedule_slot__quotation=schedule_config.quotation,
            schedule_slot__contract__isnull=True,
        )
        .first()
    )


def get_existing_appointment_for_patient_in_slot(*, patient, schedule_slot):
    return (
        Appointment.objects
        .select_related("schedule_slot")
        .filter(
            **_appointment_patient_filter(patient),
            schedule_slot=schedule_slot,
        )
        .first()
    )


def _schedule_slots_for_registration(*, contract=None, schedule_config=None):
    if schedule_config:
        actual_contract = _schedule_config_actual_contract(schedule_config)
        if actual_contract:
            return ScheduleSlot.objects.filter(
                contract=actual_contract,
                slot_type=SlotType.CONTRACT,
            )
        return ScheduleSlot.objects.filter(
            quotation=schedule_config.quotation,
            contract__isnull=True,
            slot_type=SlotType.CONTRACT,
        )

    return ScheduleSlot.objects.filter(contract=contract).order_by("date", "shift")


def build_patient_registration_calendar(*, contract=None, schedule_config=None):
    schedules = _schedule_slots_for_registration(
        contract=contract,
        schedule_config=schedule_config,
    ).order_by("date", "shift")
    slot_map = {(slot.date, slot.shift): slot for slot in schedules}

    start_date = getattr(schedule_config, "exam_start_date", None) if schedule_config else getattr(contract, "start_date", None)
    end_date = getattr(schedule_config, "exam_end_date", None) if schedule_config else getattr(contract, "end_date", None)

    month_list = get_month_list(start_date, end_date)
    months_data = []
    slot_status = {}

    for year_value, month_value in month_list:
        num_days = calendar.monthrange(year_value, month_value)[1]
        days_in_month = [date(year_value, month_value, d) for d in range(1, num_days + 1)]
        schedule_data = {}

        for day in days_in_month:
            in_range = start_date <= day <= end_date
            day_data = {}
            any_open = False

            for shift_label, shift_value in [
                ("MORNING", TimeShift.MORNING),
                ("AFTERNOON", TimeShift.AFTERNOON),
            ]:
                slot = slot_map.get((day, shift_value))

                if slot:
                    remaining = max(0, (slot.capacity or 0) - (slot.booked_count or 0))
                    max_slot = slot.capacity or 0
                else:
                    remaining = 0
                    max_slot = 0

                if in_range and remaining > 0:
                    any_open = True

                day_data[shift_label] = {
                    "remaining": remaining if in_range else 0,
                    "max": max_slot if in_range else 0,
                    "disabled": (not in_range) or remaining == 0,
                    "schedule_id": slot.id if slot else None,
                }

            day_data["disabled_all"] = (not in_range) or (not any_open)
            schedule_data[str(day)] = day_data
            slot_status[str(day)] = {
                "am": day_data["MORNING"]["remaining"],
                "pm": day_data["AFTERNOON"]["remaining"],
            }

        weeks = list(calendar.Calendar(firstweekday=0).monthdatescalendar(year_value, month_value))
        months_data.append({
            "year": year_value,
            "month": month_value,
            "weeks": weeks,
            "schedule_data": schedule_data,
        })

    return {
        "months_data": months_data,
        "slot_status": slot_status,
    }


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
