from dataclasses import dataclass, field

from django.db import IntegrityError, transaction

from apps.contract.domain.exceptions import (
    ContractPermissionDenied,
    ContractValidationError,
)
from apps.contract.models import BloodCollectionSchedule, Contract
from apps.contract.models.contract import ContractStatus
from apps.contract.policies import ContractPolicy
from apps.contract.services.common import (
    money_to_vietnamese_words,
    parse_date,
    parse_datetime_local,
    parse_int,
    parse_money,
    reserve_next_contract_number,
)
from apps.organizations.models import Company
from apps.organizations.selectors.company_selectors import get_company_for_actor


@dataclass(frozen=True)
class BloodCollectionRow:
    collection_date: object
    location: str = ""
    people_count: int = 0
    staff_count: int = 0


@dataclass(frozen=True)
class CreateContractCommand:
    company_id: int
    company_address: str = ""
    company_phone: str = ""
    tax_code: str = ""
    contact_person: str = ""
    representative_title: str = ""
    employee_count: int = 0
    start_date: object = None
    end_date: object = None
    reception_from_date: object = None
    contract_value_text: str = ""
    deposit_payment_text: str = ""
    settlement_time_text: str = ""
    note: str = ""
    blood_collection_rows: list = field(default_factory=list)
    actor: object = None


def _normalize_text(value):
    return str(value or "").strip()


def _normalize_blood_rows(rows, *, actor):
    clean_rows = []
    allow_staff = ContractPolicy.is_nurse(actor)

    for idx, row in enumerate(rows, start=1):
        d_obj = parse_date(row.collection_date, required=True, field_label=f"ngày lấy máu dòng {idx}")
        loc = _normalize_text(row.location)
        ppl = parse_int(row.people_count, 0)
        stf = parse_int(row.staff_count, 0) if allow_staff else 0

        if not d_obj and not loc and not ppl and not stf:
            continue

        clean_rows.append(
            BloodCollectionRow(
                collection_date=d_obj,
                location=loc,
                people_count=ppl,
                staff_count=stf,
            )
        )

    return clean_rows


def _validate_command(cmd: CreateContractCommand):
    if not cmd.company_id:
        raise ContractValidationError("Vui lòng chọn công ty.")

    employee_count = parse_int(cmd.employee_count, 0)
    if employee_count <= 0:
        raise ContractValidationError("Số lượng nhân viên phải lớn hơn 0.")

    start_date = parse_date(cmd.start_date, required=True, field_label="ngày bắt đầu")
    end_date = parse_date(cmd.end_date, required=True, field_label="ngày kết thúc")
    reception_from_date = parse_date(cmd.reception_from_date, required=False, field_label="ngày tiếp nhận")

    if end_date < start_date:
        raise ContractValidationError("Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.")

    return {
        "company_address": _normalize_text(cmd.company_address),
        "company_phone": _normalize_text(cmd.company_phone),
        "tax_code": _normalize_text(cmd.tax_code),
        "contact_person": _normalize_text(cmd.contact_person),
        "representative_title": _normalize_text(cmd.representative_title),
        "employee_count": employee_count,
        "start_date": start_date,
        "end_date": end_date,
        "reception_from_date": reception_from_date,
        "contract_value_text": _normalize_text(cmd.contract_value_text) or None,
        "deposit_payment_text": _normalize_text(cmd.deposit_payment_text) or None,
        "settlement_time_text": _normalize_text(cmd.settlement_time_text) or None,
        "note": _normalize_text(cmd.note) or None,
    }


@transaction.atomic
def execute(cmd: CreateContractCommand):
    if not ContractPolicy.can_create(cmd.actor):
        raise ContractPermissionDenied("Bạn không có quyền tạo hợp đồng.")

    company = get_company_for_actor(user=cmd.actor, company_id=cmd.company_id)
    if not company:
        raise ContractPermissionDenied("Bạn không có quyền truy cập công ty này.")

    payload = _validate_command(cmd)
    blood_rows = _normalize_blood_rows(cmd.blood_collection_rows or [], actor=cmd.actor)

    legacy_company = Company.objects.select_for_update().get(pk=company.id)

    dirty_company = False
    if payload["company_address"] and legacy_company.address != payload["company_address"]:
        legacy_company.address = payload["company_address"]
        dirty_company = True
    if payload["company_phone"] and legacy_company.phone != payload["company_phone"]:
        legacy_company.phone = payload["company_phone"]
        dirty_company = True
    if payload["tax_code"] and legacy_company.tax_code != payload["tax_code"]:
        legacy_company.tax_code = payload["tax_code"]
        dirty_company = True

    if dirty_company:
        legacy_company.save(update_fields=["address", "phone", "tax_code"])

    try:
        contract = Contract.objects.create(
            company=legacy_company,
            contract_number=reserve_next_contract_number(),
            contact_person=payload["contact_person"],
            representative_title=payload["representative_title"],
            employee_count=payload["employee_count"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            reception_from_date=payload["reception_from_date"],
            contract_value_text=payload["contract_value_text"],
            deposit_payment_text=payload["deposit_payment_text"],
            settlement_time_text=payload["settlement_time_text"],
            note=payload["note"],
            status=ContractStatus.SUBMITTED,
            created_by=cmd.actor if getattr(cmd.actor, "is_authenticated", False) else None,
        )
    except IntegrityError as exc:
        raise ContractValidationError(f"Lỗi trùng số hợp đồng: {exc}")

    if blood_rows:
        BloodCollectionSchedule.objects.bulk_create(
            [
                BloodCollectionSchedule(
                    contract=contract,
                    collection_date=row.collection_date,
                    location=row.location,
                    people_count=row.people_count,
                    staff_count=row.staff_count,
                )
                for row in blood_rows
            ],
            batch_size=100,
        )

    from apps.scheduling.services.allocate_slots import allocate_contract_slots
    allocate_contract_slots(contract=contract, actor=cmd.actor)

    return contract