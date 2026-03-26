from dataclasses import dataclass, field

from django.db import transaction

from apps.contract.models import BloodCollectionSchedule, Contract
from apps.organizations.models import Company
from apps.contract.domain.exceptions import (
    ContractPermissionDenied,
    ContractValidationError,
)
from apps.contract.policies import ContractPolicy
from apps.contract.services.common import parse_date, parse_int
from apps.organizations.selectors.company_selectors import get_company_for_actor


@dataclass(frozen=True)
class BloodCollectionRow:
    collection_date: object
    location: str = ""
    people_count: int = 0
    staff_count: int = 0


@dataclass(frozen=True)
class UpdateContractCommand:
    contract_id: int
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


def _normalize_rows(rows, *, actor):
    allow_staff = ContractPolicy.is_nurse(actor)
    clean_rows = []

    for idx, row in enumerate(rows, start=1):
        if (
            not str(getattr(row, "collection_date", "") or "").strip()
            and not str(getattr(row, "location", "") or "").strip()
            and not parse_int(getattr(row, "people_count", 0), 0)
            and not parse_int(getattr(row, "staff_count", 0), 0)
        ):
            continue

        clean_rows.append(
            BloodCollectionRow(
                collection_date=parse_date(
                    getattr(row, "collection_date", None),
                    required=True,
                    field_label=f"ngày lấy máu dòng {idx}",
                ),
                location=_normalize_text(getattr(row, "location", "")),
                people_count=parse_int(getattr(row, "people_count", 0), 0),
                staff_count=parse_int(getattr(row, "staff_count", 0), 0) if allow_staff else 0,
            )
        )

    return clean_rows


@transaction.atomic
def execute(cmd: UpdateContractCommand):
    contract = Contract.objects.select_for_update().filter(pk=cmd.contract_id).first()
    if not contract:
        raise ContractValidationError("Không tìm thấy hợp đồng.")

    if not ContractPolicy.can_update(cmd.actor, contract):
        raise ContractPermissionDenied("Bạn không có quyền sửa hợp đồng này.")

    company = get_company_for_actor(user=cmd.actor, company_id=cmd.company_id)
    if not company:
        raise ContractPermissionDenied("Bạn không có quyền truy cập công ty này.")

    employee_count = parse_int(cmd.employee_count, 0)
    if employee_count <= 0:
        raise ContractValidationError("Số lượng nhân viên phải lớn hơn 0.")

    start_date = parse_date(cmd.start_date, required=True, field_label="ngày bắt đầu")
    end_date = parse_date(cmd.end_date, required=True, field_label="ngày kết thúc")
    reception_from_date = parse_date(cmd.reception_from_date, required=False, field_label="ngày tiếp nhận")

    if end_date < start_date:
        raise ContractValidationError("Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.")

    legacy_company = Company.objects.select_for_update().get(pk=company.id)
    company_address = _normalize_text(cmd.company_address)
    company_phone = _normalize_text(cmd.company_phone)
    tax_code = _normalize_text(cmd.tax_code)

    dirty_company = False
    if company_address and legacy_company.address != company_address:
        legacy_company.address = company_address
        dirty_company = True
    if company_phone and legacy_company.phone != company_phone:
        legacy_company.phone = company_phone
        dirty_company = True
    if tax_code and legacy_company.tax_code != tax_code:
        legacy_company.tax_code = tax_code
        dirty_company = True
    if dirty_company:
        legacy_company.save(update_fields=["address", "phone", "tax_code"])

    contract.company = legacy_company
    contract.contact_person = _normalize_text(cmd.contact_person)
    contract.representative_title = _normalize_text(cmd.representative_title)
    contract.employee_count = employee_count
    contract.start_date = start_date
    contract.end_date = end_date
    contract.reception_from_date = reception_from_date
    contract.contract_value_text = _normalize_text(cmd.contract_value_text) or None
    contract.deposit_payment_text = _normalize_text(cmd.deposit_payment_text) or None
    contract.settlement_time_text = _normalize_text(cmd.settlement_time_text) or None
    contract.note = _normalize_text(cmd.note) or None
    contract.save()

    rows = _normalize_rows(cmd.blood_collection_rows or [], actor=cmd.actor)
    BloodCollectionSchedule.objects.filter(contract_id=contract.id).delete()
    if rows:
        BloodCollectionSchedule.objects.bulk_create(
            [
                BloodCollectionSchedule(
                    contract=contract,
                    collection_date=row.collection_date,
                    location=row.location,
                    people_count=row.people_count,
                    staff_count=row.staff_count,
                )
                for row in rows
            ],
            batch_size=100,
        )

    from apps.scheduling.services.allocate_slots import allocate_contract_slots
    allocate_contract_slots(contract=contract, actor=cmd.actor)

    return contract