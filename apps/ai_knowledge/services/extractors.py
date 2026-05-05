from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from apps.ai_knowledge.models import AIKnowledgeSource
from apps.booking.models import Appointment, IndividualBooking
from apps.catalogs.models import CheckupCategory, CheckupPackageTemplate, GroupCheckup
from apps.clinical.models import DentalExamination, PathologyResult
from apps.contract.models import Contract, ContractServiceLine, CorporateContractProfile
from apps.contract.models.document import DocumentTemplate, IssuedDocument
from apps.contract.models.implementation import ImplementationPlan
from apps.contract.models.quotation import QuotationDraft
from apps.engagement.models.channel import CannedResponse, Conversation
from apps.hrm.models.department import Department, Position
from apps.hrm.models.doctor_schedule import DoctorSchedule
from apps.hrm.models.employee import Employee
from apps.organizations.models import Company
from apps.patients.models.patients import Patient
from apps.procedures.models import Procedure
from apps.quality.models import IncidentReport, MedicalRecordAudit
from apps.reception.models import CheckInRecord
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot, SlotType

from .clean_text import clean_text


SUPPORTED_SOURCE_TYPES = [
    AIKnowledgeSource.SOURCE_PROCEDURE,
    AIKnowledgeSource.SOURCE_CATEGORY,
    AIKnowledgeSource.SOURCE_PACKAGE,
    AIKnowledgeSource.SOURCE_SERVICE,
    AIKnowledgeSource.SOURCE_FAQ,
    AIKnowledgeSource.SOURCE_CONTRACT,
    AIKnowledgeSource.SOURCE_QUOTATION,
    AIKnowledgeSource.SOURCE_POLICY,
    AIKnowledgeSource.SOURCE_PATIENT_SUMMARY,
    AIKnowledgeSource.SOURCE_VISIT_SUMMARY,
    AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
    AIKnowledgeSource.SOURCE_MEDICAL_RECORD,
    AIKnowledgeSource.SOURCE_DOCUMENT,
    AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
]


@dataclass
class SourceDocument:
    source_type: str
    source_id: str
    title: str
    content: str
    metadata: dict
    access_level: str = AIKnowledgeSource.ACCESS_INTERNAL
    locale: str = "vi"
    source_url: str = ""
    source_updated_at: datetime | None = None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256((self.content or "").encode("utf-8")).hexdigest()


def _join_non_empty(parts: Iterable[str]) -> str:
    return "\n".join(part.strip() for part in parts if part and str(part).strip())


def _json_text(value) -> str:
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False)


def _fmt_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _fmt_datetime(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    return str(value)


def _fmt_money(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, Decimal):
        value = int(value)
    try:
        return f"{int(value):,} VND".replace(",", ".")
    except Exception:
        return str(value)


def _variant_source_id(prefix: str, raw_id) -> str:
    return f"{prefix}:{raw_id}"


def _parse_variant_source_id(source_id: str | None) -> tuple[str, str | None]:
    if not source_id:
        return "", None
    value = str(source_id)
    if ":" not in value:
        return "", value
    prefix, raw_id = value.split(":", 1)
    return prefix, raw_id


def _matches_variant(source_id: str | None, *, prefix: str) -> tuple[bool, str | None]:
    if source_id is None:
        return True, None
    current_prefix, raw_id = _parse_variant_source_id(source_id)
    return current_prefix == prefix, raw_id


def _patient_name(patient, his_patient) -> str:
    return (
        getattr(his_patient, "full_name", None)
        or getattr(patient, "ho_ten", None)
        or "Khong ro"
    )


def _patient_code(patient, his_patient) -> str:
    return (
        getattr(his_patient, "his_patient_code", None)
        or getattr(patient, "ma_bn", None)
        or ""
    )


def _build_group_document(group: GroupCheckup) -> SourceDocument:
    categories = list(group.categories.filter(is_active=True).order_by("display_order", "pk")[:20])
    category_names = ", ".join(item.item_name for item in categories)
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_SERVICE,
        source_id=_variant_source_id("group", group.pk),
        title=group.name,
        content=_join_non_empty(
            [
                "Loai du lieu: Nhom dich vu cong khai",
                f"Nhom kham: {group.name}",
                f"Ten tieng Anh: {group.group_en}" if group.group_en else "",
                f"So danh muc dang hoat dong: {group.categories.filter(is_active=True).count()}",
                f"Danh muc tieu bieu: {category_names}" if category_names else "",
            ]
        ),
        metadata={
            "group_id": group.pk,
            "visibility": "public",
            "section_key": f"group-{group.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_PUBLIC,
        source_updated_at=group.updated_at,
    )


def _build_category_document(category: CheckupCategory) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_CATEGORY,
        source_id=str(category.pk),
        title=category.item_name,
        content=_join_non_empty(
            [
                "Loai tai lieu: Danh muc kham",
                f"Nhom: {category.group_checkup.name}",
                f"Tieu nhom: {category.subgroup_name}" if category.subgroup_name else "",
                f"Hang muc: {category.item_name}",
                f"Ma: {category.item_code}" if category.item_code else "",
                clean_text(category.description or ""),
                f"Gia niem yet: {_fmt_money(category.list_price)}" if category.list_price is not None else "",
                f"Loai gia: {category.get_price_type_display()}",
                f"Ghi chu: {category.note}" if category.note else "",
            ]
        ),
        metadata={
            "group_name": category.group_checkup.name,
            "group_id": category.group_checkup_id,
            "item_code": category.item_code,
            "price_type": category.price_type,
            "for_male": category.for_male,
            "for_female_single": category.for_female_single,
            "for_female_family": category.for_female_family,
            "visibility": "public",
            "section_key": f"category-{category.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_PUBLIC,
        source_updated_at=category.updated_at,
    )


def _build_package_document(package: CheckupPackageTemplate) -> SourceDocument:
    item_blocks = []
    for item in package.items.select_related("category", "category__group_checkup").all():
        category = item.category
        item_blocks.append(
            _join_non_empty(
                [
                    f"Hang muc: {category.item_name}",
                    f"Nhom: {category.group_checkup.name}",
                    f"Gia niem yet: {_fmt_money(category.list_price)}",
                    clean_text(category.description or ""),
                ]
            )
        )

    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_PACKAGE,
        source_id=str(package.pk),
        title=package.name,
        content=_join_non_empty(
            [
                "Loai tai lieu: Goi kham mau",
                f"Ten goi: {package.name}",
                clean_text(package.description or ""),
                f"So hang muc: {package.items.count()}",
                f"Gia tri danh nghia: {_fmt_money(package.total_list_price)}",
                "\n\n".join(item_blocks),
            ]
        ),
        metadata={
            "item_count": package.items.count(),
            "visibility": "public",
            "section_key": f"package-{package.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_PUBLIC,
        source_updated_at=package.updated_at,
    )


def _build_procedure_document(procedure: Procedure) -> SourceDocument:
    step_blocks = []
    for step in procedure.steps.all().order_by("order", "pk"):
        step_blocks.append(
            _join_non_empty(
                [
                    f"Buoc: {step.title}",
                    f"Phu trach: {step.responsible}" if step.responsible else "",
                    f"Thoi gian: {step.duration}" if step.duration else "",
                    clean_text(step.description),
                ]
            )
        )
    access_level = (
        AIKnowledgeSource.ACCESS_CLINICAL
        if procedure.category == "clinical"
        else AIKnowledgeSource.ACCESS_INTERNAL
    )
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_PROCEDURE,
        source_id=str(procedure.pk),
        title=procedure.title,
        content=_join_non_empty(
            [
                "Loai tai lieu: Quy trinh noi bo",
                f"Tieu de: {procedure.title}",
                f"Ma quy trinh: {procedure.code}" if procedure.code else "",
                f"Loai: {procedure.get_category_display()}",
                f"Phien ban: {procedure.version}",
                f"Ngay hieu luc: {_fmt_date(procedure.effective_date)}" if procedure.effective_date else "",
                clean_text(procedure.description),
                "\n\n".join(step_blocks),
            ]
        ),
        metadata={
            "code": procedure.code,
            "category": procedure.category,
            "status": procedure.status,
            "section_key": f"procedure-{procedure.pk}",
        },
        access_level=access_level,
        source_updated_at=procedure.updated_at,
    )


def _build_public_doctor_schedule_document(schedule: DoctorSchedule) -> SourceDocument:
    doctor = schedule.doctor
    schedule_text = _json_text(schedule.get_schedule_display())
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_SERVICE,
        source_id=_variant_source_id("doctor-schedule", schedule.pk),
        title=f"Lich bac si {doctor.full_name}",
        content=_join_non_empty(
            [
                "Loai du lieu: Lich kham bac si cong khai",
                f"Bac si: {doctor.full_name}",
                f"Chuc vu: {getattr(doctor.position, 'name', '')}" if getattr(doctor, "position_id", None) else "",
                f"Khoa/phong: {getattr(doctor.department, 'name', '')}" if getattr(doctor, "department_id", None) else "",
                f"Tuan bat dau: {_fmt_date(schedule.week_start)}",
                schedule_text,
            ]
        ),
        metadata={
            "doctor_id": doctor.pk,
            "department": getattr(getattr(doctor, "department", None), "name", ""),
            "visibility": "public",
            "section_key": f"doctor-schedule-{schedule.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_PUBLIC,
        source_updated_at=schedule.updated_at,
    )


def _build_internal_doctor_schedule_document(schedule: DoctorSchedule) -> SourceDocument:
    doctor = schedule.doctor
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
        source_id=_variant_source_id("doctor-schedule", schedule.pk),
        title=f"Lich lam viec bac si {doctor.full_name}",
        content=_join_non_empty(
            [
                "Loai du lieu: Lich lam viec bac si noi bo",
                f"Bac si: {doctor.full_name}",
                f"Ma nhan vien: {doctor.employee_code}",
                f"Phong ban: {getattr(doctor.department, 'name', '')}" if doctor.department_id else "",
                f"Chuc vu: {getattr(doctor.position, 'name', '')}" if doctor.position_id else "",
                f"Tuan bat dau: {_fmt_date(schedule.week_start)}",
                _json_text(schedule.get_schedule_display()),
                f"Ghi chu: {schedule.note}" if schedule.note else "",
            ]
        ),
        metadata={
            "doctor_id": doctor.pk,
            "department": getattr(getattr(doctor, "department", None), "name", ""),
            "owner_id": getattr(getattr(schedule, "created_by", None), "id", None),
            "section_key": f"doctor-schedule-internal-{schedule.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=schedule.updated_at,
    )


def _build_company_document(company: Company) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_DOCUMENT,
        source_id=_variant_source_id("company", company.pk),
        title=company.name,
        content=_join_non_empty(
            [
                "Loai tai lieu: Ho so cong ty",
                f"Ten cong ty: {company.name}",
                f"Dia chi: {company.address}" if company.address else "",
                f"Ma so thue: {company.tax_code}" if company.tax_code else "",
                f"So dien thoai: {company.phone}" if company.phone else "",
            ]
        ),
        metadata={
            "company_id": company.pk,
            "owner_id": company.created_by_id,
            "section_key": f"company-{company.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=company.updated_at,
    )


def _build_employee_document(employee: Employee) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
        source_id=_variant_source_id("employee", employee.pk),
        title=employee.full_name,
        content=_join_non_empty(
            [
                "Loai tai lieu: Ho so nhan su noi bo",
                f"Nhan vien: {employee.full_name}",
                f"Ma nhan vien: {employee.employee_code}",
                f"Phong ban: {getattr(employee.department, 'name', '')}" if employee.department_id else "",
                f"Chuc vu: {getattr(employee.position, 'name', '')}" if employee.position_id else "",
                f"Loai hinh cong viec: {employee.get_employment_type_display()}",
                f"Trang thai: {employee.get_status_display()}",
                f"Quan ly truc tiep: {getattr(employee.direct_manager, 'full_name', '')}" if employee.direct_manager_id else "",
                f"Ngay vao lam: {_fmt_date(employee.hire_date)}" if employee.hire_date else "",
                f"Ghi chu: {employee.note}" if employee.note else "",
            ]
        ),
        metadata={
            "department": getattr(getattr(employee, "department", None), "name", ""),
            "department_id": employee.department_id,
            "owner_id": employee.user_id or employee.created_by_id,
            "section_key": f"employee-{employee.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=employee.updated_at,
    )


def _build_department_document(department: Department) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
        source_id=_variant_source_id("department", department.pk),
        title=department.name,
        content=_join_non_empty(
            [
                "Loai tai lieu: Co cau phong ban",
                f"Phong ban: {department.name}",
                f"Ma: {department.code}" if department.code else "",
                f"Cap tren: {department.parent.name}" if department.parent_id else "",
                clean_text(department.description or ""),
            ]
        ),
        metadata={
            "department": department.name,
            "department_id": department.pk,
            "section_key": f"department-{department.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=department.updated_at,
    )


def _build_position_document(position: Position) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
        source_id=_variant_source_id("position", position.pk),
        title=position.name,
        content=_join_non_empty(
            [
                "Loai tai lieu: Chuc danh noi bo",
                f"Chuc danh: {position.name}",
                f"Ma: {position.code}" if position.code else "",
                f"Phong ban: {position.department.name}" if position.department_id else "",
                f"Cap bac: {position.level}",
            ]
        ),
        metadata={
            "department": getattr(getattr(position, "department", None), "name", ""),
            "department_id": position.department_id,
            "section_key": f"position-{position.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=position.updated_at,
    )


def _build_contract_document(contract: Contract) -> SourceDocument:
    line_blocks = []
    for line in contract.service_lines.all().order_by("display_order", "pk"):
        line_blocks.append(
            _join_non_empty(
                [
                    f"Dich vu: {line.item_name}",
                    f"Mo ta: {clean_text(line.description or '')}" if line.description else "",
                    f"Ghi chu: {line.note}" if line.note else "",
                    f"Gia nam: {_fmt_money(line.price_male)}" if line.price_male else "",
                    f"Gia nu doc than: {_fmt_money(line.price_female_single)}" if line.price_female_single else "",
                    f"Gia nu gia dinh: {_fmt_money(line.price_female_family)}" if line.price_female_family else "",
                ]
            )
        )
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_CONTRACT,
        source_id=str(contract.pk),
        title=contract.contract_number or f"Hop dong #{contract.pk}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Hop dong doanh nghiep",
                f"So hop dong: {contract.contract_number}" if contract.contract_number else "",
                f"Cong ty: {contract.company.name}",
                f"Trang thai: {contract.get_status_display()}",
                f"So nhan su: {contract.employee_count}" if contract.employee_count else "",
                f"Tu ngay: {_fmt_date(contract.start_date)}" if contract.start_date else "",
                f"Den ngay: {_fmt_date(contract.end_date)}" if contract.end_date else "",
                f"Gia tri hop dong: {clean_text(contract.contract_value_text or '')}" if contract.contract_value_text else "",
                f"Thong tin dat coc: {clean_text(contract.deposit_payment_text or '')}" if contract.deposit_payment_text else "",
                f"Thanh toan: {clean_text(contract.settlement_time_text or '')}" if contract.settlement_time_text else "",
                f"Ghi chu: {clean_text(contract.note or '')}" if contract.note else "",
                "\n\n".join(line_blocks),
            ]
        ),
        metadata={
            "company_id": contract.company_id,
            "contract_id": contract.pk,
            "owner_id": contract.created_by_id,
            "section_key": f"contract-{contract.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CONTRACT,
        source_updated_at=contract.updated_at,
    )


def _build_quotation_document(quotation: QuotationDraft) -> SourceDocument:
    line_blocks = []
    for line in quotation.lines.all().order_by("display_order", "pk"):
        line_blocks.append(
            _join_non_empty(
                [
                    f"Hang muc: {line.item_name}",
                    f"Nhom: {line.group_name}" if line.group_name else "",
                    f"Mo ta: {clean_text(line.description or '')}" if line.description else "",
                    f"Gia nam: {_fmt_money(line.price_male)}" if line.price_male else "",
                    f"Gia nu doc than: {_fmt_money(line.price_female_single)}" if line.price_female_single else "",
                    f"Gia nu gia dinh: {_fmt_money(line.price_female_family)}" if line.price_female_family else "",
                    f"Ghi chu: {line.note}" if line.note else "",
                ]
            )
        )
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_QUOTATION,
        source_id=str(quotation.pk),
        title=f"Bao gia {quotation.company_name}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Bao gia doanh nghiep",
                f"Cong ty: {quotation.company_name}",
                f"Lien he: {quotation.contact_name}" if quotation.contact_name else "",
                f"So dien thoai: {quotation.contact_phone}" if quotation.contact_phone else "",
                f"Trang thai: {quotation.get_status_display()}",
                f"Hieu luc den: {_fmt_date(quotation.valid_until)}" if quotation.valid_until else "",
                f"So nguoi tu: {quotation.pax_from}" if quotation.pax_from else "",
                f"Tong gia tri: {_fmt_money(quotation.grand_total)}",
                clean_text(quotation.note or ""),
                clean_text(quotation.extra_content or ""),
                "\n\n".join(line_blocks),
            ]
        ),
        metadata={
            "company_id": quotation.company_id,
            "quotation_id": quotation.pk,
            "owner_id": quotation.created_by_id,
            "section_key": f"quotation-{quotation.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CONTRACT,
        source_updated_at=quotation.updated_at,
    )


def _build_implementation_plan_document(plan: ImplementationPlan) -> SourceDocument:
    contract = plan.contract
    corporate_profile = getattr(contract, "corporate_profile", None)
    quotation = getattr(corporate_profile, "quotation", None)
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_DOCUMENT,
        source_id=_variant_source_id("plan", plan.pk),
        title=f"Ke hoach trien khai {contract.contract_number or contract.pk}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Ke hoach trien khai hop dong",
                f"Hop dong: {contract.contract_number}" if contract.contract_number else "",
                f"Bao gia: #{quotation.pk}" if quotation is not None else "",
                f"Cong ty: {contract.company.name}",
                f"Ngay bat dau: {_fmt_date(contract.start_date)}" if contract.start_date else "",
                f"Ngay ket thuc: {_fmt_date(contract.end_date)}" if contract.end_date else "",
                f"Cong khai: {'Co' if plan.is_published else 'Khong'}",
                _json_text(plan.rows_json),
            ]
        ),
        metadata={
            "company_id": contract.company_id,
            "contract_id": contract.pk,
            "quotation_id": getattr(quotation, "pk", None),
            "section_key": f"implementation-plan-{plan.pk}",
        },
        access_level=(
            AIKnowledgeSource.ACCESS_CONTRACT
            if plan.is_published
            else AIKnowledgeSource.ACCESS_MANAGER
        ),
        source_updated_at=plan.updated_at,
    )


def _build_schedule_config_document(config: ContractScheduleConfig) -> SourceDocument:
    blood_rows = [
        _join_non_empty(
            [
                f"Ngay lay mau: {_fmt_date(row.collection_date)}",
                f"Dia diem: {row.location}" if row.location else "",
                f"So nguoi: {row.people_count}",
                f"So dieu duong: {row.staff_count}",
            ]
        )
        for row in config.blood_collection_rows.all().order_by("collection_date", "pk")
    ]
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_DOCUMENT,
        source_id=_variant_source_id("schedule", config.pk),
        title=f"Lich kham doanh nghiep quotation #{config.quotation_id}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Cau hinh lich kham doanh nghiep",
                f"Bao gia: #{config.quotation_id}",
                f"Tu ngay: {_fmt_date(config.exam_start_date)}",
                f"Den ngay: {_fmt_date(config.exam_end_date)}",
                f"So nguoi du kien: {config.planned_employee_count}",
                f"Gioi han slot sang: {config.am_capacity_limit}",
                f"Gioi han slot chieu: {config.pm_capacity_limit}",
                f"Thu duoc phep: {_json_text(config.allowed_weekdays)}",
                f"Da chot: {'Co' if config.is_confirmed else 'Khong'}",
                f"Da ket thuc: {'Co' if config.is_ended else 'Khong'}",
                "\n\n".join(blood_rows),
            ]
        ),
        metadata={
            "quotation_id": config.quotation_id,
            "contract_id": getattr(config.contract, "contract_id", None),
            "company_id": getattr(getattr(config.contract, "contract", None), "company_id", None),
            "section_key": f"schedule-config-{config.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CONTRACT,
        source_updated_at=config.updated_at,
    )


def _build_public_slot_document(slot: ScheduleSlot) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_SERVICE,
        source_id=_variant_source_id("slot", slot.pk),
        title=f"Lich kham {slot.date} {slot.get_shift_display()}",
        content=_join_non_empty(
            [
                "Loai du lieu: Slot lich kham cong khai",
                f"Ngay: {_fmt_date(slot.date)}",
                f"Buoi: {slot.get_shift_display()}",
                f"Suc chua: {slot.capacity}",
                f"Con trong: {slot.remaining_capacity}",
                f"Trang thai: {slot.get_status_display()}",
                f"Ghi chu: {slot.note}" if slot.note else "",
            ]
        ),
        metadata={
            "slot_id": slot.pk,
            "section_key": f"slot-public-{slot.pk}",
            "visibility": "public",
        },
        access_level=AIKnowledgeSource.ACCESS_PUBLIC,
        source_updated_at=slot.updated_at,
    )


def _build_contract_slot_document(slot: ScheduleSlot) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_DOCUMENT,
        source_id=_variant_source_id("slot-contract", slot.pk),
        title=f"Slot hop dong {slot.date} {slot.get_shift_display()}",
        content=_join_non_empty(
            [
                "Loai du lieu: Slot lich kham hop dong",
                f"Ngay: {_fmt_date(slot.date)}",
                f"Buoi: {slot.get_shift_display()}",
                f"Suc chua: {slot.capacity}",
                f"Da dang ky: {slot.booked_count}",
                f"Trang thai: {slot.get_status_display()}",
                f"Hop dong: #{slot.contract_id}" if slot.contract_id else "",
                f"Bao gia: #{slot.quotation_id}" if slot.quotation_id else "",
                f"Ghi chu: {slot.note}" if slot.note else "",
            ]
        ),
        metadata={
            "contract_id": slot.contract_id,
            "quotation_id": slot.quotation_id,
            "company_id": getattr(getattr(slot, "contract", None), "company_id", None),
            "section_key": f"slot-contract-{slot.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CONTRACT,
        source_updated_at=slot.updated_at,
    )


def _build_policy_document(template: DocumentTemplate) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_POLICY,
        source_id=str(template.pk),
        title=template.name,
        content=_join_non_empty(
            [
                "Loai tai lieu: Mau van ban hop dong/bao gia",
                f"Ten mau: {template.name}",
                f"Code: {template.code}",
                f"Loai: {template.get_doc_type_display()}",
                f"Phien ban: {template.version}",
                f"Trang thai: {'Dang dung' if template.is_active else 'Khong hoat dong'}",
            ]
        ),
        metadata={
            "doc_type": template.doc_type,
            "section_key": f"policy-{template.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=template.updated_at,
    )


def _build_patient_summary_document(patient: Patient) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_PATIENT_SUMMARY,
        source_id=str(patient.pk),
        title=f"Benh nhan {patient.ho_ten}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Tom tat benh nhan",
                f"Ma benh nhan: {patient.ma_bn}",
                f"Ho ten: {patient.ho_ten}",
                f"Gioi tinh: {patient.gioi_tinh}",
                f"Ngay sinh: {_fmt_date(patient.ngay_sinh)}" if patient.ngay_sinh else "",
                f"Cong ty: {patient.company.name}" if patient.company_id else "",
                f"Vi tri cong tac: {patient.position}" if patient.position else "",
            ]
        ),
        metadata={
            "patient_id": patient.pk,
            "company_id": patient.company_id,
            "section_key": f"patient-{patient.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_PATIENT,
        source_updated_at=patient.updated_at,
    )


def _build_appointment_document(appointment: Appointment) -> SourceDocument:
    patient = appointment.patient
    his_patient = appointment.his_patient_sync
    slot = appointment.schedule_slot
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_VISIT_SUMMARY,
        source_id=_variant_source_id("appointment", appointment.pk),
        title=f"Lich hen {_patient_name(patient, his_patient)}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Tom tat lich hen/visit",
                f"Benh nhan: {_patient_name(patient, his_patient)}",
                f"Ma benh nhan: {_patient_code(patient, his_patient)}",
                f"Trang thai: {appointment.get_status_display()}",
                f"Ngay kham: {_fmt_date(slot.date)}",
                f"Buoi: {slot.get_shift_display()}",
                f"Ghi chu: {appointment.note}" if appointment.note else "",
            ]
        ),
        metadata={
            "patient_id": patient.pk if patient else None,
            "visit_id": appointment.pk,
            "company_id": getattr(getattr(slot, "contract", None), "company_id", None),
            "section_key": f"appointment-{appointment.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CLINICAL,
        source_updated_at=appointment.updated_at,
    )


def _build_checkin_document(record: CheckInRecord) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_VISIT_SUMMARY,
        source_id=_variant_source_id("checkin", record.pk),
        title=f"Check-in {record.snapshot_ho_ten}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Tom tat tiep nhan/check-in",
                f"Benh nhan: {record.snapshot_ho_ten}",
                f"Ma benh nhan: {record.snapshot_ma_bn}",
                f"Gioi tinh: {record.snapshot_gioi_tinh}" if record.snapshot_gioi_tinh else "",
                f"Ngay sinh: {_fmt_date(record.snapshot_ngay_sinh)}" if record.snapshot_ngay_sinh else "",
                f"Cong ty: {record.snapshot_company_name}" if record.snapshot_company_name else "",
                f"Ngay kham thuc te: {_fmt_date(record.exam_date)}",
                f"Trang thai: {record.get_status_display()}",
                f"Check-in luc: {_fmt_datetime(record.checked_in_at)}" if record.checked_in_at else "",
                f"Check-out luc: {_fmt_datetime(record.checked_out_at)}" if record.checked_out_at else "",
                f"Ghi chu: {record.note}" if record.note else "",
            ]
        ),
        metadata={
            "patient_id": record.patient_id,
            "company_id": record.company_id,
            "visit_id": record.pk,
            "section_key": f"checkin-{record.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CLINICAL,
        source_updated_at=record.updated_at,
    )


def _build_individual_booking_document(booking: IndividualBooking) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
        source_id=_variant_source_id("booking", booking.pk),
        title=f"Yeu cau dat kham {booking.full_name}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Yeu cau dat kham khach le",
                f"Khach hang: {booking.full_name}",
                f"So dien thoai: {booking.phone}",
                f"Ngay sinh: {_fmt_date(booking.dob)}" if booking.dob else "",
                f"Trang thai: {booking.get_status_display()}",
                f"Nguon: {booking.get_source_display()}",
                f"Ly do kham: {booking.reason}" if booking.reason else "",
                f"Ghi chu: {booking.note}" if booking.note else "",
                f"Slot: {_fmt_date(booking.schedule_slot.date)} {booking.schedule_slot.get_shift_display()}",
            ]
        ),
        metadata={
            "patient_id": booking.patient_id,
            "owner_id": booking.created_by_id,
            "section_key": f"booking-{booking.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=booking.updated_at,
    )


def _build_dental_examination_document(exam: DentalExamination) -> SourceDocument:
    patient = exam.patient
    his_patient = exam.his_patient
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
        source_id=_variant_source_id("dental", exam.pk),
        title=f"Kham rang ham mat {_patient_name(patient, his_patient)}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Ghi chu lam sang",
                f"Benh nhan: {_patient_name(patient, his_patient)}",
                f"Ma benh nhan: {_patient_code(patient, his_patient)}",
                f"Cong ty: {exam.company.name}" if exam.company_id else "",
                f"Phan loai mat rang: {exam.tooth_loss_classification}" if exam.tooth_loss_classification else "",
                f"Kha nang nhai: {exam.chewing_ability}" if exam.chewing_ability is not None else "",
                f"Xep loai suc khoe: {exam.health_classification}" if exam.health_classification else "",
                f"Ket luan: {clean_text(exam.conclusion or '')}" if exam.conclusion else "",
                f"Ghi chu bo sung: {clean_text(exam.additional_notes or '')}" if exam.additional_notes else "",
            ]
        ),
        metadata={
            "patient_id": exam.patient_id,
            "company_id": exam.company_id,
            "medical_record_id": exam.pk,
            "section_key": f"dental-{exam.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CLINICAL,
        source_updated_at=exam.updated_at,
    )


def _build_pathology_document(result: PathologyResult) -> SourceDocument:
    patient = result.patient
    his_patient = result.his_patient
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_MEDICAL_RECORD,
        source_id=str(result.pk),
        title=f"Ket qua GPB {_patient_name(patient, his_patient)}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Ho so can lam sang/medical record",
                f"Benh nhan: {_patient_name(patient, his_patient)}",
                f"Ma benh nhan: {_patient_code(patient, his_patient)}",
                f"Vi tri: {result.location}",
                f"Ngay ket qua: {_fmt_date(result.result_date)}" if result.result_date else "",
                f"Ket luan tu dong: {clean_text(result.auto_extracted_conclusion or '')}" if result.auto_extracted_conclusion else "",
                f"Ket luan thu cong: {clean_text(result.manual_conclusion or '')}" if result.manual_conclusion else "",
                f"Danh gia: {result.get_evaluation_display()}" if result.evaluation else "",
            ]
        ),
        metadata={
            "patient_id": result.patient_id,
            "medical_record_id": result.pk,
            "section_key": f"pathology-{result.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_CLINICAL,
        source_updated_at=result.updated_at,
    )


def _build_medical_record_audit_document(audit: MedicalRecordAudit) -> SourceDocument:
    passed, total, percent = audit.calc_score()
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
        source_id=_variant_source_id("audit", audit.pk),
        title=f"Audit ho so {audit.patient_name}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Danh gia chat luong ho so",
                f"Benh nhan: {audit.patient_name}",
                f"Ma benh nhan/ho so: {audit.patient_code}" if audit.patient_code else "",
                f"Ngay kham: {_fmt_date(audit.visit_date)}" if audit.visit_date else "",
                f"Phong kham/chuyen khoa: {audit.clinic_room}" if audit.clinic_room else "",
                f"Bac si: {audit.doctor_name}" if audit.doctor_name else "",
                f"Diem dat: {passed}/{total}" if total else "",
                f"Ty le: {percent}%" if percent is not None else "",
                f"Nhan xet chung: {clean_text(audit.overall_comment or '')}" if audit.overall_comment else "",
            ]
        ),
        metadata={
            "patient_code": audit.patient_code,
            "department": audit.clinic_room,
            "medical_record_id": audit.pk,
            "section_key": f"audit-{audit.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_MANAGER,
        source_updated_at=audit.updated_at,
    )


def _build_incident_document(incident: IncidentReport) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
        source_id=_variant_source_id("incident", incident.pk),
        title=f"Su co {incident.pk}",
        content=_join_non_empty(
            [
                "Loai tai lieu: Bao cao su co/rui ro",
                f"Bo phan: {incident.department}" if incident.department else "",
                f"Nguoi bao cao: {incident.reporter_name}" if incident.reporter_name else "",
                f"Phan loai: {incident.get_incident_type_display()}",
                f"Ten su co: {incident.get_incident_name_display()}" if incident.incident_name else "",
                f"Thoi diem: {_fmt_datetime(incident.incident_datetime)}" if incident.incident_datetime else "",
                f"Vi tri: {incident.location}" if incident.location else "",
                f"Quy trinh lien quan: {clean_text(incident.related_policy or '')}" if incident.related_policy else "",
                f"Mo ta: {clean_text(incident.description or '')}",
                f"Hau qua: {clean_text(incident.consequence or '')}" if incident.consequence else "",
            ]
        ),
        metadata={
            "department": incident.department,
            "patient_code": incident.patient_code,
            "owner_id": incident.reported_by_id,
            "section_key": f"incident-{incident.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_MANAGER,
        source_updated_at=incident.updated_at,
    )


def _build_canned_response_document(response: CannedResponse, *, access_level: str, prefix: str, source_type: str) -> SourceDocument:
    return SourceDocument(
        source_type=source_type,
        source_id=_variant_source_id(prefix, response.pk),
        title=response.title,
        content=_join_non_empty(
            [
                "Loai tai lieu: Mau tra loi nhanh",
                f"Tieu de: {response.title}",
                f"Phim tat: /{response.shortcut}",
                f"Kenh ap dung: {_json_text(response.channel_types)}" if response.channel_types else "",
                clean_text(response.content or ""),
            ]
        ),
        metadata={
            "owner_id": response.created_by_id,
            "section_key": f"{prefix}-{response.pk}",
        },
        access_level=access_level,
        source_updated_at=response.created_at,
    )


def _build_conversation_document(conversation: Conversation) -> SourceDocument:
    return SourceDocument(
        source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
        source_id=_variant_source_id("conversation", conversation.pk),
        title=conversation.customer_name or conversation.external_id,
        content=_join_non_empty(
            [
                "Loai tai lieu: Tom tat hoi thoai CSKH",
                f"Khach hang: {conversation.customer_name or conversation.external_id}",
                f"Kenh: {conversation.channel.name}",
                f"Trang thai: {conversation.get_status_display()}",
                f"Uu tien: {conversation.get_priority_display()}",
                f"Chu de: {conversation.subject}" if conversation.subject else "",
                f"Cong ty lien ket: {conversation.linked_company.name}" if conversation.linked_company_id else "",
                f"Ghi chu noi bo: {clean_text(conversation.internal_note or '')}" if conversation.internal_note else "",
                f"CSAT: {conversation.csat_score}" if conversation.csat_score else "",
                f"Nhan xet CSAT: {clean_text(conversation.csat_comment or '')}" if conversation.csat_comment else "",
            ]
        ),
        metadata={
            "company_id": conversation.linked_company_id,
            "owner_id": conversation.assigned_to_id,
            "section_key": f"conversation-{conversation.pk}",
        },
        access_level=AIKnowledgeSource.ACCESS_INTERNAL,
        source_updated_at=conversation.updated_at,
    )


def _list_service_documents(source_id: str | None = None) -> list[SourceDocument]:
    documents: list[SourceDocument] = []

    matched, raw_id = _matches_variant(source_id, prefix="group")
    if matched:
        queryset = GroupCheckup.objects.filter(is_active=True).order_by("display_order", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_group_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="doctor-schedule")
    if matched:
        queryset = DoctorSchedule.objects.select_related("doctor", "doctor__department", "doctor__position").order_by("-week_start", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_public_doctor_schedule_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="slot")
    if matched:
        queryset = ScheduleSlot.objects.filter(slot_type=SlotType.INDIVIDUAL).order_by("date", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_public_slot_document(item) for item in queryset)

    return documents


def _list_faq_documents(source_id: str | None = None) -> list[SourceDocument]:
    matched, raw_id = _matches_variant(source_id, prefix="faq")
    if not matched:
        return []
    queryset = CannedResponse.objects.order_by("title", "pk")
    if raw_id is not None:
        queryset = queryset.filter(pk=raw_id)
    documents: list[SourceDocument] = []
    for item in queryset:
        channel_types = set(item.channel_types or [])
        if channel_types and "WEBCHAT" not in channel_types:
            continue
        documents.append(
            _build_canned_response_document(
                item,
                access_level=AIKnowledgeSource.ACCESS_PUBLIC,
                prefix="faq",
                source_type=AIKnowledgeSource.SOURCE_FAQ,
            )
        )
    return documents


def _list_document_documents(source_id: str | None = None) -> list[SourceDocument]:
    documents: list[SourceDocument] = []

    matched, raw_id = _matches_variant(source_id, prefix="company")
    if matched:
        queryset = Company.objects.order_by("pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_company_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="plan")
    if matched:
        queryset = (
            ImplementationPlan.objects
            .select_related("contract", "contract__company", "contract__corporate_profile", "contract__corporate_profile__quotation")
            .order_by("pk")
        )
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_implementation_plan_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="schedule")
    if matched:
        queryset = (
            ContractScheduleConfig.objects
            .select_related("quotation", "contract", "contract__contract")
            .prefetch_related("blood_collection_rows")
            .order_by("pk")
        )
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_schedule_config_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="slot-contract")
    if matched:
        queryset = (
            ScheduleSlot.objects
            .select_related("contract", "quotation")
            .filter(slot_type=SlotType.CONTRACT)
            .order_by("date", "pk")
        )
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_contract_slot_document(item) for item in queryset)

    return documents


def _list_internal_note_documents(source_id: str | None = None) -> list[SourceDocument]:
    documents: list[SourceDocument] = []

    matched, raw_id = _matches_variant(source_id, prefix="doctor-schedule")
    if matched:
        queryset = DoctorSchedule.objects.select_related("doctor", "doctor__department", "doctor__position", "created_by").order_by("-week_start", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_internal_doctor_schedule_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="employee")
    if matched:
        queryset = Employee.objects.select_related("department", "position", "direct_manager", "user", "created_by").order_by("full_name", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_employee_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="department")
    if matched:
        queryset = Department.objects.select_related("parent").filter(is_active=True).order_by("display_order", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_department_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="position")
    if matched:
        queryset = Position.objects.select_related("department").filter(is_active=True).order_by("-level", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_position_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="booking")
    if matched:
        queryset = IndividualBooking.objects.select_related("schedule_slot", "created_by", "patient").order_by("-created_at", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_individual_booking_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="incident")
    if matched:
        queryset = IncidentReport.objects.select_related("reported_by").order_by("-created_at", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_incident_document(item) for item in queryset)

    matched, raw_id = _matches_variant(source_id, prefix="response")
    if matched:
        queryset = CannedResponse.objects.order_by("title", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(
            _build_canned_response_document(
                item,
                access_level=AIKnowledgeSource.ACCESS_INTERNAL,
                prefix="response",
                source_type=AIKnowledgeSource.SOURCE_INTERNAL_NOTE,
            )
            for item in queryset
        )

    matched, raw_id = _matches_variant(source_id, prefix="conversation")
    if matched:
        queryset = Conversation.objects.select_related("channel", "linked_company", "assigned_to").order_by("-updated_at", "pk")
        if raw_id is not None:
            queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_conversation_document(item) for item in queryset)

    return documents


def _list_supported_source_documents(
    source_types: list[str] | None = None,
    source_id: str | None = None,
) -> list[SourceDocument]:
    source_types = source_types or SUPPORTED_SOURCE_TYPES
    documents: list[SourceDocument] = []

    if AIKnowledgeSource.SOURCE_PROCEDURE in source_types:
        queryset = Procedure.objects.filter(status="published").prefetch_related("steps").order_by("pk")
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_procedure_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_CATEGORY in source_types:
        queryset = (
            CheckupCategory.objects
            .filter(is_active=True, group_checkup__is_active=True)
            .select_related("group_checkup")
            .order_by("group_checkup__display_order", "display_order", "pk")
        )
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_category_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_PACKAGE in source_types:
        queryset = (
            CheckupPackageTemplate.objects
            .filter(is_active=True)
            .prefetch_related("items", "items__category", "items__category__group_checkup")
            .order_by("pk")
        )
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_package_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_SERVICE in source_types:
        documents.extend(_list_service_documents(source_id))

    if AIKnowledgeSource.SOURCE_FAQ in source_types:
        documents.extend(_list_faq_documents(source_id))

    if AIKnowledgeSource.SOURCE_CONTRACT in source_types:
        queryset = (
            Contract.objects
            .select_related("company", "created_by")
            .prefetch_related("service_lines")
            .order_by("pk")
        )
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_contract_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_QUOTATION in source_types:
        queryset = (
            QuotationDraft.objects
            .select_related("company", "created_by")
            .prefetch_related("lines")
            .order_by("pk")
        )
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_quotation_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_POLICY in source_types:
        queryset = DocumentTemplate.objects.order_by("pk")
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_policy_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_PATIENT_SUMMARY in source_types:
        queryset = Patient.objects.select_related("company").order_by("pk")
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_patient_summary_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_VISIT_SUMMARY in source_types:
        matched, raw_id = _matches_variant(source_id, prefix="appointment")
        if matched:
            queryset = (
                Appointment.objects
                .select_related("patient", "his_patient_sync", "schedule_slot", "schedule_slot__contract")
                .order_by("pk")
            )
            if raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
            documents.extend(_build_appointment_document(item) for item in queryset)

        matched, raw_id = _matches_variant(source_id, prefix="checkin")
        if matched:
            queryset = CheckInRecord.objects.select_related("patient", "his_patient_sync", "company").order_by("pk")
            if raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
            documents.extend(_build_checkin_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_CLINICAL_NOTE in source_types:
        matched, raw_id = _matches_variant(source_id, prefix="dental")
        if matched:
            queryset = DentalExamination.objects.select_related("patient", "his_patient", "company").order_by("pk")
            if raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
            documents.extend(_build_dental_examination_document(item) for item in queryset)

        matched, raw_id = _matches_variant(source_id, prefix="audit")
        if matched:
            queryset = MedicalRecordAudit.objects.select_related("created_by").order_by("pk")
            if raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
            documents.extend(_build_medical_record_audit_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_MEDICAL_RECORD in source_types:
        queryset = PathologyResult.objects.select_related("patient", "his_patient").order_by("pk")
        if source_id is not None:
            prefix, raw_id = _parse_variant_source_id(source_id)
            if prefix:
                queryset = queryset.none()
            elif raw_id is not None:
                queryset = queryset.filter(pk=raw_id)
        documents.extend(_build_pathology_document(item) for item in queryset)

    if AIKnowledgeSource.SOURCE_DOCUMENT in source_types:
        documents.extend(_list_document_documents(source_id))

    if AIKnowledgeSource.SOURCE_INTERNAL_NOTE in source_types:
        documents.extend(_list_internal_note_documents(source_id))

    return documents


def list_source_documents(
    source_types: list[str] | None = None,
    source_id: str | None = None,
) -> list[SourceDocument]:
    return _list_supported_source_documents(source_types=source_types, source_id=source_id)


def extract_text_for_source(source_type: str, source_id: str) -> SourceDocument:
    documents = list_source_documents(source_types=[source_type], source_id=str(source_id))
    if not documents:
        raise ValueError(f"Unsupported or missing source: {source_type}:{source_id}")
    return documents[0]
