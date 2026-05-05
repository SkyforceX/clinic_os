from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from apps.ai_assistant.models import Conversation
from apps.ai_assistant.selectors import (
    count_appointments_for_user,
    count_checkins_for_user,
    count_companies_for_user,
    count_contracts_for_user,
    count_employees_for_user,
    count_patients_for_user,
    count_quotations_for_user,
    list_appointment_summaries_for_user,
    list_checkin_summaries_for_user,
    list_contract_summaries_for_user,
    list_overdue_record_completion_summaries_for_user,
    list_quotation_summaries_for_user,
    list_top_checkin_companies_for_user,
    list_top_contract_companies_for_user,
    list_top_quotation_companies_for_user,
)
from apps.booking.models import IndividualBooking
from apps.catalogs.models import CheckupCategory, CheckupPackageTemplate
from apps.clinical.models import DentalExamination, PathologyResult
from apps.contract.models import ContractStatus
from apps.contract.models.quotation import QuotationStatus
from apps.engagement.models.channel import Conversation as EngagementConversation
from apps.hrm.models.doctor_schedule import DoctorSchedule
from apps.organizations.selectors.company_selectors import list_companies_for_actor
from apps.quality.models import IncidentReport, MedicalRecordAudit
from apps.reception.models import CheckInStatus
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot

from .nlu_planner import route_structured_tool_call


COUNT_PATTERNS = (
    "bao nhieu",
    "co may",
    "so luong",
    "tong so",
)
LIST_PATTERNS = (
    "liet ke",
    "danh sach",
    "show",
)
ATTENTION_PATTERNS = (
    "qua han",
    "can chu y",
    "cho xu ly",
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents)


def _is_count_question(normalized: str) -> bool:
    return any(pattern in normalized for pattern in COUNT_PATTERNS)


def _is_list_question(normalized: str) -> bool:
    return any(pattern in normalized for pattern in LIST_PATTERNS)


def _is_attention_question(normalized: str) -> bool:
    return any(pattern in normalized for pattern in ATTENTION_PATTERNS)


def _mentions_today(normalized: str) -> bool:
    return "hom nay" in normalized or "ngay hom nay" in normalized


def _extract_explicit_date(normalized: str):
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", normalized)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return datetime(int(year), int(month), int(day)).date()
    except ValueError:
        return None


def _mentions_top(normalized: str) -> bool:
    return "top" in normalized or "nhieu nhat" in normalized


def _mentions_appointment_booking(normalized: str) -> bool:
    return any(
        term in normalized
        for term in (
            "lich hen",
            "dang ky kham",
            "ca dang ky kham",
            "lich dang ky kham",
        )
    )


def _quotation_status(normalized: str) -> str | None:
    if "cho duyet" in normalized:
        return QuotationStatus.SUBMITTED
    if "da duyet" in normalized:
        return QuotationStatus.APPROVED
    if "tu choi" in normalized:
        return QuotationStatus.REJECTED
    if "nhap" in normalized or "ban nhap" in normalized:
        return QuotationStatus.DRAFT
    return None


def _contract_status(normalized: str) -> tuple[str | None, bool]:
    if "dang hieu luc" in normalized or "hieu luc" in normalized:
        return None, True
    if "cho duyet" in normalized:
        return ContractStatus.SUBMITTED, False
    if "da duyet" in normalized:
        return ContractStatus.APPROVED, False
    if "hoan tat" in normalized:
        return ContractStatus.FINISHED, False
    if "cham dut" in normalized:
        return ContractStatus.TERMINATED, False
    if "huy" in normalized:
        return ContractStatus.CANCELLED, False
    if "nhap" in normalized:
        return ContractStatus.DRAFT, False
    return None, False


def _appointment_status(normalized: str) -> str | None:
    if "cho xac nhan" in normalized:
        return "PENDING"
    if "da xac nhan" in normalized:
        return "CONFIRMED"
    if "check in" in normalized or "checkin" in normalized:
        return "CHECKED_IN"
    if "dang kham" in normalized:
        return "IN_PROGRESS"
    if "hoan thanh" in normalized:
        return "COMPLETED"
    if "huy" in normalized:
        return "CANCELLED"
    if "vang" in normalized:
        return "NO_SHOW"
    return None


def _checkin_status(normalized: str) -> str | None:
    if "check out" in normalized or "checkout" in normalized:
        return CheckInStatus.CHECKED_OUT
    if "quay lai sau" in normalized or "deferred" in normalized or "hoan lai" in normalized:
        return CheckInStatus.DEFERRED
    if "check in" in normalized or "checkin" in normalized:
        return CheckInStatus.CHECKED_IN
    return None


def _extract_company_name(user, normalized: str) -> str | None:
    if "cong ty" not in normalized:
        return None
    companies = list_companies_for_actor(user)
    matches: list[str] = []
    for company in companies:
        company_name = (getattr(company, "name", "") or "").strip()
        normalized_company_name = _normalize_text(company_name)
        if normalized_company_name and normalized_company_name in normalized:
            matches.append(company_name)
    if not matches:
        return None
    return max(matches, key=len)


def _render_count_answer(*, label: str, count: int, qualifier: str = "") -> str:
    suffix = f" {qualifier.strip()}" if qualifier else ""
    return f"Hiện tại có {count} {label}{suffix}."


def _render_top_companies_answer(title: str, rows: list[dict]) -> str:
    if not rows:
        return f"Hiện chưa có dữ liệu để tổng hợp {title}"
    parts = [title]
    for index, row in enumerate(rows, start=1):
        parts.append(f"{index}. {row['company_name']}: {row['total']}")
    return "\n".join(parts)


def _render_item_list(title: str, rows: list[str]) -> str:
    if not rows:
        return f"Hiện chưa có dữ liệu phù hợp cho {title.lower()}."
    parts = [title]
    for index, row in enumerate(rows, start=1):
        parts.append(f"{index}. {row}")
    return "\n".join(parts)


def _format_quotation_status(status: str) -> str:
    return {
        QuotationStatus.DRAFT: "nháp",
        QuotationStatus.SUBMITTED: "chờ duyệt",
        QuotationStatus.APPROVED: "đã duyệt",
        QuotationStatus.REJECTED: "bị từ chối",
    }.get(status, status)


def _format_contract_status(status: str) -> str:
    return {
        ContractStatus.DRAFT: "nháp",
        ContractStatus.SUBMITTED: "chờ duyệt",
        ContractStatus.APPROVED: "đã duyệt",
        ContractStatus.ACTIVE: "đang hiệu lực",
        ContractStatus.FINISHED: "hoàn tất",
        ContractStatus.TERMINATED: "chấm dứt",
        ContractStatus.CANCELLED: "đã hủy",
    }.get(status, status)


def _format_appointment_status(status: str) -> str:
    return {
        "PENDING": "chờ xác nhận",
        "CONFIRMED": "đã xác nhận",
        "CHECKED_IN": "đã check-in",
        "IN_PROGRESS": "đang khám",
        "COMPLETED": "hoàn thành",
        "CANCELLED": "đã hủy",
        "NO_SHOW": "vắng",
    }.get(status, status)


def _format_checkin_status(status: str) -> str:
    return {
        CheckInStatus.CHECKED_IN: "đã check-in",
        CheckInStatus.CHECKED_OUT: "đã check-out",
        CheckInStatus.DEFERRED: "quay lại sau",
    }.get(status, status)


def _render_quotation_list(rows: list[dict]) -> str:
    return _render_item_list(
        "Danh sách báo giá:",
        [
            f"BG#{row['id']} - {row['company_name']} - {_format_quotation_status(row['status'])}"
            + (f" - hết hạn {row['valid_until']:%d/%m/%Y}" if row["valid_until"] else "")
            for row in rows
        ],
    )


def _render_contract_list(rows: list[dict]) -> str:
    return _render_item_list(
        "Danh sách hợp đồng:",
        [
            f"{row['contract_number']} - {row['company_name']} - {_format_contract_status(row['status'])}"
            + (f" - kết thúc {row['end_date']:%d/%m/%Y}" if row["end_date"] else "")
            for row in rows
        ],
    )


def _render_appointment_list(rows: list[dict]) -> str:
    return _render_item_list(
        "Danh sách lịch hẹn:",
        [
            f"LH#{row['id']} - {row['patient_name']} - {_format_appointment_status(row['status'])}"
            + (f" - {row['date']:%d/%m/%Y}" if row["date"] else "")
            for row in rows
        ],
    )


def _render_checkin_list(rows: list[dict]) -> str:
    return _render_item_list(
        "Danh sách check-in:",
        [
            f"{row['patient_code']} - {row['patient_name']} - {row['company_name']} - {_format_checkin_status(row['status'])}"
            + (f" - {row['exam_date']:%d/%m/%Y}" if row["exam_date"] else "")
            for row in rows
        ],
    )


def _render_overdue_completion_list(rows: list[dict]) -> str:
    return _render_item_list(
        "Danh sách hồ sơ quá hạn cần chú ý:",
        [
            f"{row['patient_code']} - {row['patient_name']} - {row['company_name']} - quá hạn {row['days_overdue']} ngày - bước {row['current_step']}"
            + (f" - khám {row['exam_date']:%d/%m/%Y}" if row["exam_date"] else "")
            for row in rows
        ],
    )


def _count_public_services() -> int:
    return CheckupCategory.objects.filter(
        is_active=True,
        group_checkup__is_active=True,
    ).count()


def _count_public_packages() -> int:
    return CheckupPackageTemplate.objects.filter(is_active=True).count()


def _count_public_doctor_schedules() -> int:
    return DoctorSchedule.objects.count()


def _count_individual_bookings() -> int:
    return IndividualBooking.objects.count()


def _count_schedule_slots() -> int:
    return ScheduleSlot.objects.count()


def _count_schedule_configs() -> int:
    return ContractScheduleConfig.objects.count()


def _count_incidents() -> int:
    return IncidentReport.objects.count()


def _count_quality_audits() -> int:
    return MedicalRecordAudit.objects.count()


def _count_conversations() -> int:
    return EngagementConversation.objects.count()


def _count_clinical_notes() -> int:
    return DentalExamination.objects.count()


def _count_medical_records() -> int:
    return PathologyResult.objects.count()


def route_tool_call(*, user, question: str, profile: str = Conversation.PROFILE_MANAGER) -> str | None:
    structured_response = route_structured_tool_call(
        user=user,
        question=question,
        profile=profile,
    )
    if structured_response is not None:
        return structured_response

    normalized = _normalize_text(question)
    is_count = _is_count_question(normalized)
    is_list = _is_list_question(normalized)
    is_attention = _is_attention_question(normalized)
    if not (is_count or is_list or is_attention or _mentions_top(normalized)):
        return None

    if profile == Conversation.PROFILE_CUSTOMER:
        if not is_count:
            return None
        if "dich vu" in normalized or "hang muc" in normalized:
            return _render_count_answer(label="dịch vụ công khai", count=_count_public_services())
        if "goi kham" in normalized:
            return _render_count_answer(label="gói khám công khai", count=_count_public_packages())
        if "bac si" in normalized or "lich bac si" in normalized:
            return _render_count_answer(
                label="lịch bác sĩ công khai",
                count=_count_public_doctor_schedules(),
            )
        return None

    company_name = _extract_company_name(user, normalized)

    if is_attention and ("ho so" in normalized or "record" in normalized):
        rows = list_overdue_record_completion_summaries_for_user(
            user,
            company_name=company_name,
        )
        if rows is None:
            return "Bạn không có quyền xem hồ sơ quá hạn."
        return _render_overdue_completion_list(rows)

    if "nhan vien" in normalized and is_count:
        count = count_employees_for_user(user)
        if count is None:
            return "Bạn không có quyền xem thống kê nhân viên."
        return _render_count_answer(label="nhân viên", count=count)

    if "bao gia" in normalized:
        status = _quotation_status(normalized)
        today_only = _mentions_today(normalized)
        if _mentions_top(normalized) and "cong ty" in normalized:
            rows = list_top_quotation_companies_for_user(
                user,
                status=status,
                created_today=today_only,
            )
            if rows is None:
                return "Bạn không có quyền xem thống kê báo giá."
            return _render_top_companies_answer("Top công ty theo số lượng báo giá:", rows)
        if is_list or is_attention:
            rows = list_quotation_summaries_for_user(
                user,
                status=status,
                created_today=today_only,
                company_name=company_name,
            )
            if rows is None:
                return "Bạn không có quyền xem danh sách báo giá."
            return _render_quotation_list(rows)
        if is_count:
            count = count_quotations_for_user(
                user,
                status=status,
                created_today=today_only,
                company_name=company_name,
            )
            if count is None:
                return "Bạn không có quyền xem thống kê báo giá."
            qualifier_parts = []
            if status:
                qualifier_parts.append(_format_quotation_status(status))
            if company_name:
                qualifier_parts.append(f"của công ty {company_name}")
            if today_only:
                qualifier_parts.append("hôm nay")
            qualifier = " ".join(qualifier_parts)
            return _render_count_answer(label="báo giá", count=count, qualifier=qualifier)

    if "hop dong" in normalized:
        status, active_only = _contract_status(normalized)
        today_only = _mentions_today(normalized)
        if _mentions_top(normalized) and "cong ty" in normalized:
            rows = list_top_contract_companies_for_user(
                user,
                status=status,
                created_today=today_only,
                active_only=active_only,
            )
            if rows is None:
                return "Bạn không có quyền xem thống kê hợp đồng."
            return _render_top_companies_answer("Top công ty theo số lượng hợp đồng:", rows)
        if is_list or is_attention:
            rows = list_contract_summaries_for_user(
                user,
                status=status,
                created_today=today_only,
                active_only=active_only,
                company_name=company_name,
            )
            if rows is None:
                return "Bạn không có quyền xem danh sách hợp đồng."
            return _render_contract_list(rows)
        if is_count:
            count = count_contracts_for_user(
                user,
                status=status,
                created_today=today_only,
                active_only=active_only,
                company_name=company_name,
            )
            if count is None:
                return "Bạn không có quyền xem thống kê hợp đồng."
            qualifier_parts = []
            if active_only:
                qualifier_parts.append("đang hiệu lực")
            elif status:
                qualifier_parts.append(_format_contract_status(status))
            if company_name:
                qualifier_parts.append(f"của công ty {company_name}")
            if today_only:
                qualifier_parts.append("hôm nay")
            qualifier = " ".join(qualifier_parts)
            return _render_count_answer(label="hợp đồng", count=count, qualifier=qualifier)

    if "cong ty" in normalized and is_count and ("bao nhieu cong ty" in normalized or "tong so cong ty" in normalized):
        count = count_companies_for_user(user)
        if count is None:
            return "Bạn không có quyền xem thống kê công ty."
        return _render_count_answer(label="công ty", count=count)

    if "benh nhan" in normalized and is_count:
        count = count_patients_for_user(user)
        if count is None:
            return "Bạn không có quyền xem thống kê bệnh nhân."
        return _render_count_answer(label="bệnh nhân", count=count)

    if _mentions_appointment_booking(normalized):
        status = _appointment_status(normalized)
        target_date = _extract_explicit_date(normalized)
        today_only = _mentions_today(normalized)
        if is_list or is_attention:
            rows = list_appointment_summaries_for_user(
                user,
                status=status,
                today_only=today_only,
                target_date=target_date,
            )
            if rows is None:
                return "Bạn không có quyền xem danh sách lịch hẹn."
            return _render_appointment_list(rows)
        if is_count:
            count = count_appointments_for_user(
                user,
                status=status,
                today_only=today_only,
                target_date=target_date,
            )
            if count is None:
                return "Bạn không có quyền xem thống kê lịch hẹn."
            qualifier_parts = []
            if status:
                qualifier_parts.append(_format_appointment_status(status))
            if target_date:
                qualifier_parts.append(f"ngay {target_date:%d/%m/%Y}")
            if today_only:
                qualifier_parts.append("hôm nay")
            qualifier = " ".join(qualifier_parts)
            return _render_count_answer(label="lịch hẹn", count=count, qualifier=qualifier)

    if "dang ky khach le" in normalized or "booking" in normalized:
        if is_count:
            return _render_count_answer(
                label="yêu cầu đặt khám khách lẻ",
                count=_count_individual_bookings(),
            )
        return None

    if "slot" in normalized or "lich kham" in normalized:
        if is_count:
            return _render_count_answer(label="slot lịch", count=_count_schedule_slots())
        return None

    if "cau hinh lich" in normalized:
        if is_count:
            return _render_count_answer(
                label="cấu hình lịch doanh nghiệp",
                count=_count_schedule_configs(),
            )
        return None

    if "check in" in normalized or "checkin" in normalized:
        status = _checkin_status(normalized)
        today_only = _mentions_today(normalized)
        if _mentions_top(normalized) and "cong ty" in normalized:
            rows = list_top_checkin_companies_for_user(
                user,
                status=status,
                today_only=today_only,
            )
            if rows is None:
                return "Bạn không có quyền xem thống kê check-in."
            return _render_top_companies_answer("Top công ty theo số lượng check-in:", rows)
        if is_list or is_attention:
            rows = list_checkin_summaries_for_user(
                user,
                status=status,
                today_only=today_only,
                company_name=company_name,
            )
            if rows is None:
                return "Bạn không có quyền xem danh sách check-in."
            return _render_checkin_list(rows)
        if is_count:
            count = count_checkins_for_user(
                user,
                status=status,
                today_only=today_only,
                company_name=company_name,
            )
            if count is None:
                return "Bạn không có quyền xem thống kê check-in."
            qualifier_parts = []
            if status:
                qualifier_parts.append(_format_checkin_status(status))
            if company_name:
                qualifier_parts.append(f"của công ty {company_name}")
            if today_only:
                qualifier_parts.append("hôm nay")
            qualifier = " ".join(qualifier_parts)
            return _render_count_answer(label="bản ghi check-in", count=count, qualifier=qualifier)

    if "su co" in normalized or "incident" in normalized:
        if is_count:
            return _render_count_answer(label="báo cáo sự cố", count=_count_incidents())
        return None

    if "audit" in normalized or "kiem tra ho so" in normalized:
        if is_count:
            return _render_count_answer(
                label="bản ghi audit chất lượng",
                count=_count_quality_audits(),
            )
        return None

    if "hoi thoai" in normalized or "conversation" in normalized:
        if is_count:
            return _render_count_answer(label="hội thoại CSKH", count=_count_conversations())
        return None

    if "ghi chu lam sang" in normalized or "kham rang" in normalized:
        if is_count:
            return _render_count_answer(label="ghi chú lâm sàng", count=_count_clinical_notes())
        return None

    if "ho so can lam sang" in normalized or "giai phau benh" in normalized:
        if is_count:
            return _render_count_answer(
                label="hồ sơ cận lâm sàng",
                count=_count_medical_records(),
            )
        return None

    return None

