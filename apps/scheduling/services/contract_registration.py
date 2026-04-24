from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.contract.models import BloodCollectionSchedule
from apps.contract.models.quotation import QuotationDraft
from apps.core.models import SystemGeneralSetting
from apps.scheduling.models import ContractScheduleConfig, ScheduleBloodCollectionRow
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.services.allocate_slots import allocate_contract_slots


@dataclass(frozen=True)
class BloodCollectionInputRow:
    collection_date: object
    location: str = ""
    people_count: int = 0
    staff_count: int = 0


@dataclass(frozen=True)
class RegisterContractScheduleCommand:
    quotation_id: int
    exam_start_date: object
    exam_end_date: object
    planned_employee_count: int
    am_capacity_limit: int
    pm_capacity_limit: int
    blood_collection_rows: list = field(default_factory=list)
    allowed_weekdays: list = field(default_factory=list)
    actor: object = None


def _parse_date(value, label):
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value

    raw = str(value or "").strip()
    if not raw:
        raise ValidationError(f"Thiếu {label}.")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    raise ValidationError(f"{label} không hợp lệ.")


def _parse_int(value, default=0):
    try:
        return int(str(value or default).strip())
    except Exception:
        return default


def _normalize_text(value):
    return str(value or "").strip()


def _validate_blood_location_limit(blood_rows, current_config_id, max_limit):
    """Kiểm tra số địa điểm lấy máu trong ngày không vượt quá giới hạn hệ thống."""
    if not max_limit or not blood_rows:
        return

    new_counts = Counter(row.collection_date for row in blood_rows)

    for blood_date, new_count in new_counts.items():
        existing_qs = ScheduleBloodCollectionRow.objects.filter(collection_date=blood_date)
        if current_config_id:
            existing_qs = existing_qs.exclude(schedule_config_id=current_config_id)
        existing_count = existing_qs.count()

        total = existing_count + new_count
        if total > max_limit:
            raise ValidationError(
                f"Ngày {blood_date.strftime('%d/%m/%Y')}: tổng số địa điểm lấy máu ({total}) "
                f"vượt quá giới hạn hệ thống ({max_limit} địa điểm/ngày)."
            )


def _normalize_blood_rows(rows):
    clean_rows = []
    for idx, row in enumerate(rows, start=1):
        raw_date = getattr(row, "collection_date", None)
        raw_location = _normalize_text(getattr(row, "location", ""))
        raw_people = _parse_int(getattr(row, "people_count", 0), 0)
        raw_staff = _parse_int(getattr(row, "staff_count", 0), 0)

        if not raw_date and not raw_location and not raw_people and not raw_staff:
            continue

        clean_rows.append(
            BloodCollectionInputRow(
                collection_date=_parse_date(raw_date, f"ngày lấy máu dòng {idx}"),
                location=raw_location,
                people_count=max(raw_people, 0),
                staff_count=max(raw_staff, 0),
            )
        )
    return clean_rows


@transaction.atomic
def execute(cmd: RegisterContractScheduleCommand):
    quotation = (
        QuotationDraft.objects
        .select_for_update()
        .filter(pk=cmd.quotation_id, company__isnull=False)
        .first()
    )
    if not quotation:
        raise ValidationError("Không tìm thấy báo giá doanh nghiệp.")
    
    linked_contract_profile = getattr(quotation, "corporate_contract_profile", None)
    linked_contract = getattr(linked_contract_profile, "contract", None)
    
    schedule_owner_id = (
        linked_contract.created_by_id
        if linked_contract and getattr(linked_contract, "created_by_id", None)
        else quotation.created_by_id
    )
    if not SchedulingPolicy.can_manage_quote_schedule(cmd.actor, schedule_owner_id):
        raise ValidationError("Bạn không có quyền đăng ký lịch khám cho báo giá này.")

    exam_start_date = _parse_date(cmd.exam_start_date, "ngày bắt đầu khám")
    exam_end_date = _parse_date(cmd.exam_end_date, "ngày kết thúc khám")

    if exam_end_date < exam_start_date:
        raise ValidationError("Ngày kết thúc khám phải lớn hơn hoặc bằng ngày bắt đầu khám.")

    planned_employee_count = _parse_int(cmd.planned_employee_count, 0)
    if planned_employee_count <= 0:
        raise ValidationError("Số khách hàng đăng ký phải lớn hơn 0.")

    am_capacity_limit = _parse_int(cmd.am_capacity_limit, 0)
    pm_capacity_limit = _parse_int(cmd.pm_capacity_limit, 0)
    if am_capacity_limit < 0 or pm_capacity_limit < 0:
        raise ValidationError("Giới hạn slot buổi sáng và chiều không được âm.")
    if am_capacity_limit == 0 and pm_capacity_limit == 0:
        raise ValidationError("Cần ít nhất một buổi có slot lớn hơn 0 (sáng hoặc chiều).")

    allowed_weekdays = []
    for raw in (cmd.allowed_weekdays or []):
        try:
            wd = int(raw)
        except (TypeError, ValueError):
            raise ValidationError("Ngày trong tuần không hợp lệ.")
        if wd < 0 or wd > 5:
            raise ValidationError("Ngày trong tuần không hợp lệ (chỉ T2–T7).")
        allowed_weekdays.append(wd)
    allowed_weekdays = sorted(set(allowed_weekdays))

    settings = SystemGeneralSetting.get_solo()
    if am_capacity_limit > settings.default_am_slot_limit:
        raise ValidationError(
            f"Giới hạn slot sáng của lịch khám không được vượt quá giới hạn hệ thống ({settings.default_am_slot_limit})."
        )
    if pm_capacity_limit > settings.default_pm_slot_limit:
        raise ValidationError(
            f"Giới hạn slot chiều của lịch khám không được vượt quá giới hạn hệ thống ({settings.default_pm_slot_limit})."
        )

    blood_rows = _normalize_blood_rows(cmd.blood_collection_rows or [])

    # Validate giới hạn địa điểm lấy máu/ngày (không tính lại rows của config hiện tại)
    if settings.max_blood_location_per_day > 0:
        existing_config = ContractScheduleConfig.objects.filter(quotation=quotation).first()
        _validate_blood_location_limit(
            blood_rows,
            existing_config.id if existing_config else None,
            settings.max_blood_location_per_day,
        )

    config, _ = ContractScheduleConfig.objects.get_or_create(
        quotation=quotation,
        defaults={
            "contract": linked_contract_profile,
            "exam_start_date": exam_start_date,
            "exam_end_date": exam_end_date,
            "planned_employee_count": planned_employee_count,
            "am_capacity_limit": am_capacity_limit,
            "pm_capacity_limit": pm_capacity_limit,
            "registered_by": cmd.actor if getattr(cmd.actor, "is_authenticated", False) else None,
        },
    )

    config.contract = linked_contract_profile
    config.exam_start_date = exam_start_date
    config.exam_end_date = exam_end_date
    config.planned_employee_count = planned_employee_count
    config.am_capacity_limit = am_capacity_limit
    config.pm_capacity_limit = pm_capacity_limit
    config.allowed_weekdays = allowed_weekdays
    config.registered_by = cmd.actor if getattr(cmd.actor, "is_authenticated", False) else None
    config.save()
    
    ScheduleBloodCollectionRow.objects.filter(schedule_config=config).delete()
    if blood_rows:
        ScheduleBloodCollectionRow.objects.bulk_create(
            [
                ScheduleBloodCollectionRow(
                    schedule_config=config,
                    collection_date=row.collection_date,
                    location=row.location,
                    people_count=row.people_count,
                    staff_count=row.staff_count,
                )
                for row in blood_rows
            ],
            batch_size=100,
        )

    if linked_contract:
        BloodCollectionSchedule.objects.filter(contract=linked_contract).delete()
        if blood_rows:
            BloodCollectionSchedule.objects.bulk_create(
                [
                    BloodCollectionSchedule(
                        contract=linked_contract,
                        collection_date=row.collection_date,
                        location=row.location,
                        people_count=row.people_count,
                        staff_count=row.staff_count,
                    )
                    for row in blood_rows
                ],
                batch_size=100,
            )

    allocate_contract_slots(
        contract=linked_contract,
        quotation=quotation,
        actor=cmd.actor,
        start_date=exam_start_date,
        end_date=exam_end_date,
        employee_count=planned_employee_count,
        am_capacity_limit=am_capacity_limit,
        pm_capacity_limit=pm_capacity_limit,
        allowed_weekdays=allowed_weekdays or None,
    )

    return config