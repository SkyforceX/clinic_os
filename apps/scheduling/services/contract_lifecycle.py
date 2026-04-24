from collections import defaultdict
from datetime import date as date_type

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.booking.models import Appointment
from apps.core.models import SystemGeneralSetting
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType, TimeShift
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_selectors import get_contract_for_actor
from apps.scheduling.services.allocate_slots import allocate_contract_slots


def redistribute_contract_slots(*, actor, contract_id):
    contract = get_contract_for_actor(user=actor, contract_id=contract_id)
    if not contract:
        raise ValueError("Khong tim thay hop dong.")

    if not SchedulingPolicy.can_redistribute_slots(actor, contract):
        raise PermissionError("Ban khong co quyen phan bo lai slot cho hop dong nay.")

    return allocate_contract_slots(contract=contract, actor=actor)


def _config_contract_and_quotation(config):
    contract_profile = getattr(config, "contract", None)
    contract_obj = getattr(contract_profile, "contract", None) if contract_profile else None
    quotation = config.quotation
    return contract_obj, quotation


def _own_contract_slots_qs(contract_obj, quotation):
    if contract_obj:
        return ScheduleSlot.objects.filter(contract=contract_obj, slot_type=SlotType.CONTRACT)
    return ScheduleSlot.objects.filter(
        quotation=quotation,
        contract__isnull=True,
        slot_type=SlotType.CONTRACT,
    )


@transaction.atomic
def update_contract_slot_capacities(*, actor, config_id, slots_input):
    config = (
        ContractScheduleConfig.objects
        .select_related("quotation", "contract", "contract__contract")
        .filter(pk=config_id)
        .first()
    )
    if not config:
        raise ValueError("Khong tim thay cau hinh lich.")

    contract_obj, quotation = _config_contract_and_quotation(config)
    owner_id = getattr(quotation, "created_by_id", None) if quotation else None
    if not SchedulingPolicy.can_manage_quote_schedule(actor, owner_id):
        raise PermissionError("Ban khong co quyen sua slot nay.")

    new_total = sum(int(s.get("am", 0)) + int(s.get("pm", 0)) for s in slots_input)
    if new_total != config.planned_employee_count:
        raise ValidationError(
            f"Tong slot moi ({new_total}) phai bang so khach hang dang ky "
            f"({config.planned_employee_count})."
        )

    settings = SystemGeneralSetting.get_solo()
    system_am_limit = int(settings.default_am_slot_limit or 0)
    system_pm_limit = int(settings.default_pm_slot_limit or 0)
    dates = [s["date"] for s in slots_input if s.get("date")]

    own_slots_map = {
        (s.date.isoformat(), s.shift): s
        for s in _own_contract_slots_qs(contract_obj, quotation).filter(date__in=dates).select_for_update()
    }

    all_totals = defaultdict(int)
    all_totals_qs = (
        ScheduleSlot.objects
        .filter(date__in=dates)
        .values("date", "shift")
        .annotate(total=Sum("capacity"))
    )
    for item in all_totals_qs:
        all_totals[(item["date"].isoformat(), item["shift"])] = item["total"] or 0

    for item in slots_input:
        d_str = item.get("date", "")
        try:
            day = date_type.fromisoformat(d_str)
        except (ValueError, TypeError):
            raise ValidationError(f"Ngay khong hop le: {d_str}")

        for shift, new_cap_raw, sys_limit, shift_label in (
            (TimeShift.MORNING, item.get("am", 0), system_am_limit, "sang"),
            (TimeShift.AFTERNOON, item.get("pm", 0), system_pm_limit, "chieu"),
        ):
            new_cap = int(new_cap_raw)
            slot = own_slots_map.get((d_str, shift))

            booked = slot.booked_count if slot else 0
            if new_cap < booked:
                raise ValidationError(
                    f"Ngay {d_str} buoi {shift_label}: khong the giam xuong {new_cap} "
                    f"vi da co {booked} BN dang ky."
                )

            total_all = all_totals.get((d_str, shift), 0)
            own_current = slot.capacity if slot else 0
            other_total = total_all - own_current
            max_capacity = max(0, sys_limit - other_total)
            if new_cap > max_capacity:
                raise ValidationError(
                    f"Ngay {d_str} buoi {shift_label}: slot {new_cap} vuot qua "
                    f"gioi han con lai ({max_capacity})."
                )

            if new_cap <= 0:
                if slot and slot.booked_count == 0:
                    slot.delete()
                elif slot and slot.booked_count > 0:
                    slot.capacity = slot.booked_count
                    slot.save(update_fields=["capacity", "updated_at"])
                continue

            if slot:
                if slot.capacity != new_cap:
                    slot.capacity = new_cap
                    slot.save(update_fields=["capacity", "updated_at"])
                continue

            ScheduleSlot.objects.create(
                contract=contract_obj,
                quotation=quotation if not contract_obj else None,
                date=day,
                shift=shift,
                slot_type=SlotType.CONTRACT,
                capacity=new_cap,
                booked_count=0,
            )

    return config


@transaction.atomic
def delete_quote_schedule_config(*, actor, config_id):
    config = (
        ContractScheduleConfig.objects
        .select_for_update()
        .filter(pk=config_id)
        .first()
    )
    if not config:
        raise ValidationError("Khong tim thay lich dang ky kham.")

    quotation = config.quotation if config.quotation_id else None

    owner_user_id = getattr(quotation, "created_by_id", None)
    if not SchedulingPolicy.can_manage_quote_schedule(actor, owner_user_id):
        raise PermissionError("Ban khong co quyen xoa lich dang ky kham nay.")

    if config.contract_id:
        raise ValidationError(
            "Lich dang ky kham nay da gan voi hop dong, khong the xoa tu man hinh dang ky lich."
        )

    quote_slots_qs = ScheduleSlot.objects.select_for_update().filter(
        quotation_id=config.quotation_id,
        contract_id__isnull=True,
        slot_type=SlotType.CONTRACT,
    )

    has_appointments = Appointment.objects.filter(schedule_slot__in=quote_slots_qs).exists()
    if has_appointments:
        raise ValidationError(
            "Lich dang ky kham da co khach hang dat slot, khong the xoa."
        )

    quote_slots_qs.delete()
    config.delete()
    return True
