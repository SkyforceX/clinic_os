from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from apps.core.models import SystemGeneralSetting
from apps.scheduling.models import ScheduleSlot, SlotType, TimeShift


def _working_days(start_date, end_date):
    if not start_date or not end_date:
        raise ValidationError("Thiếu ngày bắt đầu hoặc ngày kết thúc khám.")

    if end_date < start_date:
        raise ValidationError("Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.")

    return [
        day
        for day in (
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
        )
        if day.weekday() != 6
    ]


def _effective_schedule_values(
    contract,
    *,
    start_date=None,
    end_date=None,
    employee_count=None,
    am_capacity_limit=None,
    pm_capacity_limit=None,
):
    config = None
    if contract:
        config = getattr(contract, "schedule_config", None)
        if config is None:
            profile = getattr(contract, "corporate_profile", None)
            config = getattr(profile, "schedule_config", None) if profile else None
    eff_start_date = start_date or getattr(config, "exam_start_date", None) or getattr(contract, "start_date", None)
    eff_end_date = end_date or getattr(config, "exam_end_date", None) or getattr(contract, "end_date", None)
    eff_employee_count = employee_count or getattr(config, "planned_employee_count", None) or getattr(contract, "employee_count", 0)
    eff_am_limit = am_capacity_limit or getattr(config, "am_capacity_limit", None)
    eff_pm_limit = pm_capacity_limit or getattr(config, "pm_capacity_limit", None)

    return {
        "start_date": eff_start_date,
        "end_date": eff_end_date,
        "employee_count": int(eff_employee_count or 0),
        "am_capacity_limit": int(eff_am_limit or 0),
        "pm_capacity_limit": int(eff_pm_limit or 0),
    }


def _owner_filter(*, contract=None, quotation=None):
    if contract is not None:
        return Q(contract=contract)
    if quotation is not None:
        return Q(quotation=quotation, contract__isnull=True)
    raise ValidationError("Thiếu đối tượng chủ sở hữu slot.")


def _exclude_current_owner(qs, *, contract=None, quotation=None):
    if contract is not None:
        return qs.exclude(contract=contract)
    if quotation is not None:
        return qs.exclude(quotation=quotation, contract__isnull=True)
    return qs


@transaction.atomic
def allocate_contract_slots(
    *,
    contract=None,
    quotation=None,
    actor=None,
    start_date=None,
    end_date=None,
    employee_count=None,
    am_capacity_limit=None,
    pm_capacity_limit=None,
):
    if contract is None and quotation is None:
        raise ValidationError("Thiếu hợp đồng hoặc báo giá để phân bổ slot.")

    values = _effective_schedule_values(
        contract,
        start_date=start_date,
        end_date=end_date,
        employee_count=employee_count,
        am_capacity_limit=am_capacity_limit,
        pm_capacity_limit=pm_capacity_limit,
    )

    total_needed = int(values["employee_count"] or 0)
    if total_needed <= 0:
        raise ValidationError("Số khách hàng đăng ký phải lớn hơn 0.")

    settings = SystemGeneralSetting.get_solo()
    system_am_limit = int(settings.default_am_slot_limit or 0)
    system_pm_limit = int(settings.default_pm_slot_limit or 0)

    requested_am_limit = int(values["am_capacity_limit"] or 0)
    requested_pm_limit = int(values["pm_capacity_limit"] or 0)

    if requested_am_limit <= 0 or requested_pm_limit <= 0:
        raise ValidationError("Giới hạn slot sáng/chiều của hợp đồng phải lớn hơn 0.")

    if requested_am_limit > system_am_limit:
        raise ValidationError(
            f"Giới hạn slot sáng của hợp đồng ({requested_am_limit}) vượt quá giới hạn hệ thống ({system_am_limit})."
        )
    if requested_pm_limit > system_pm_limit:
        raise ValidationError(
            f"Giới hạn slot chiều của hợp đồng ({requested_pm_limit}) vượt quá giới hạn hệ thống ({system_pm_limit})."
        )

    days = _working_days(values["start_date"], values["end_date"])
    if not days:
        raise ValidationError("Khoảng thời gian đăng ký không có ngày làm việc hợp lệ.")

    owner_q = _owner_filter(contract=contract, quotation=quotation)

    day_records = []
    total_available = 0

    for day in days:
        used_am = (
            _exclude_current_owner(
                ScheduleSlot.objects.filter(date=day, shift=TimeShift.MORNING),
                contract=contract,
                quotation=quotation,
            )
            .aggregate(total=Sum("capacity"))
            .get("total") or 0
        )
        used_pm = (
            _exclude_current_owner(
                ScheduleSlot.objects.filter(date=day, shift=TimeShift.AFTERNOON),
                contract=contract,
                quotation=quotation,
            )
            .aggregate(total=Sum("capacity"))
            .get("total") or 0
        )

        remaining_am = max(0, system_am_limit - used_am)
        remaining_pm = max(0, system_pm_limit - used_pm)

        contract_am_cap = min(requested_am_limit, remaining_am)
        contract_pm_cap = min(requested_pm_limit, remaining_pm)

        total_available += (contract_am_cap + contract_pm_cap)
        day_records.append(
            {
                "day": day,
                "am_cap": contract_am_cap,
                "pm_cap": contract_pm_cap,
                "am_assign": 0,
                "pm_assign": 0,
            }
        )

    if total_available < total_needed:
        raise ValidationError(
            f"Khoảng thời gian đã chọn chỉ còn {total_available} slot khả dụng cho lịch khám này, "
            f"không đủ cho {total_needed} khách hàng."
        )

    remaining = total_needed

    for idx, record in enumerate(day_records):
        if remaining <= 0:
            break

        remaining_days = len(day_records) - idx
        target_today = -(-remaining // remaining_days)
        target_today = min(target_today, record["am_cap"] + record["pm_cap"])

        am_assign = min((target_today + 1) // 2, record["am_cap"])
        pm_assign = min(target_today // 2, record["pm_cap"])

        assigned = am_assign + pm_assign
        missing = target_today - assigned

        if missing > 0:
            extra_am = min(missing, record["am_cap"] - am_assign)
            am_assign += extra_am
            missing -= extra_am

        if missing > 0:
            extra_pm = min(missing, record["pm_cap"] - pm_assign)
            pm_assign += extra_pm
            missing -= extra_pm

        record["am_assign"] = am_assign
        record["pm_assign"] = pm_assign
        remaining -= (am_assign + pm_assign)

    while remaining > 0:
        changed = False
        for record in day_records:
            if remaining <= 0:
                break

            if record["am_assign"] < record["am_cap"]:
                record["am_assign"] += 1
                remaining -= 1
                changed = True
                if remaining <= 0:
                    break

            if record["pm_assign"] < record["pm_cap"]:
                record["pm_assign"] += 1
                remaining -= 1
                changed = True

        if not changed:
            break

    if remaining > 0:
        raise ValidationError("Không thể phân bổ đủ slot theo giới hạn hiện tại.")

    planned_days = {record["day"] for record in day_records}

    for record in day_records:
        day = record["day"]
        for shift, assigned in (
            (TimeShift.MORNING, record["am_assign"]),
            (TimeShift.AFTERNOON, record["pm_assign"]),
        ):
            slot = (
                ScheduleSlot.objects
                .select_for_update()
                .filter(
                    owner_q,
                    date=day,
                    shift=shift,
                    slot_type=SlotType.CONTRACT,
                )
                .first()
            )

            if assigned <= 0:
                if slot and (slot.booked_count or 0) == 0:
                    slot.delete()
                elif slot and (slot.booked_count or 0) > 0 and slot.capacity != slot.booked_count:
                    slot.capacity = slot.booked_count
                    slot.save(update_fields=["capacity", "updated_at"])
                continue

            if slot:
                new_capacity = max(assigned, slot.booked_count or 0)
                dirty_fields = []
                if slot.capacity != new_capacity:
                    slot.capacity = new_capacity
                    dirty_fields.append("capacity")
                if quotation is not None and slot.quotation_id != quotation.id:
                    slot.quotation = quotation
                    dirty_fields.append("quotation")
                if contract is not None and slot.contract_id != contract.id:
                    slot.contract = contract
                    dirty_fields.append("contract")
                if dirty_fields:
                    dirty_fields.append("updated_at")
                    slot.save(update_fields=dirty_fields)
            else:
                ScheduleSlot.objects.create(
                    contract=contract,
                    quotation=quotation,
                    date=day,
                    shift=shift,
                    slot_type=SlotType.CONTRACT,
                    capacity=assigned,
                    booked_count=0,
                )

    stale_slots = (
        ScheduleSlot.objects
        .filter(owner_q, slot_type=SlotType.CONTRACT)
        .exclude(date__in=planned_days)
        .filter(booked_count=0)
    )
    stale_slots.delete()

    return contract or quotation