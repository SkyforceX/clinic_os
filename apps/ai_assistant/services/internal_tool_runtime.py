from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

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
from apps.booking.models import AppointmentStatus, IndividualBooking
from apps.catalogs.models import CheckupCategory, CheckupPackageTemplate
from apps.contract.models import ContractStatus
from apps.contract.models.quotation import QuotationStatus
from apps.hrm.models.doctor_schedule import DoctorSchedule
from apps.organizations.selectors.company_selectors import list_companies_for_actor
from apps.reception.models import CheckInStatus
from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot


PUBLIC_TOOL_NAMES = {
    "public_service_count",
    "public_package_count",
    "public_doctor_schedule_count",
}


@dataclass(frozen=True)
class ToolIntent:
    tool_name: str
    operation: str = "count"
    status: str | None = None
    company_name: str | None = None
    target_date: date | None = None
    today_only: bool = False
    active_only: bool = False
    limit: int = 5


def normalize_text(value: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents)


def parse_iso_or_local_date(value) -> date | None:
    if isinstance(value, date):
        return value
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw_value, fmt).date()
        except ValueError:
            continue
    return None


def extract_company_name(user, normalized_question: str, preferred_name: str | None = None) -> str | None:
    companies = list_companies_for_actor(user)
    if preferred_name:
        preferred_normalized = normalize_text(preferred_name)
        for company in companies:
            company_name = (getattr(company, "name", "") or "").strip()
            if normalize_text(company_name) == preferred_normalized:
                return company_name

    if "cong ty" not in normalized_question:
        return None

    matches: list[str] = []
    for company in companies:
        company_name = (getattr(company, "name", "") or "").strip()
        normalized_company_name = normalize_text(company_name)
        if normalized_company_name and normalized_company_name in normalized_question:
            matches.append(company_name)
    if not matches:
        return preferred_name.strip() if preferred_name else None
    return max(matches, key=len)


def _render_count_answer(*, label: str, count: int, qualifier: str = "") -> str:
    suffix = f" {qualifier.strip()}" if qualifier else ""
    return f"Hiện tại có {count} {label}{suffix}."


def _render_top_companies_answer(title: str, rows: list[dict]) -> str:
    if not rows:
        return f"Hiện chưa có dữ liệu để tổng hợp {title.lower()}"
    lines = [title]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row['company_name']}: {row['total']}")
    return "\n".join(lines)


def _render_item_list(title: str, rows: list[str]) -> str:
    if not rows:
        return f"Hiện chưa có dữ liệu phù hợp cho {title.lower()}."
    lines = [title]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row}")
    return "\n".join(lines)


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
        AppointmentStatus.PENDING: "chờ xác nhận",
        AppointmentStatus.CONFIRMED: "đã xác nhận",
        AppointmentStatus.CHECKED_IN: "đã check-in",
        AppointmentStatus.IN_PROGRESS: "đang khám",
        AppointmentStatus.COMPLETED: "hoàn thành",
        AppointmentStatus.CANCELLED: "đã hủy",
        AppointmentStatus.NO_SHOW: "vắng",
    }.get(status, status)


def _format_checkin_status(status: str) -> str:
    return {
        CheckInStatus.CHECKED_IN: "đã check-in",
        CheckInStatus.CHECKED_OUT: "đã check-out",
        CheckInStatus.DEFERRED: "quay lại sau",
    }.get(status, status)


def _build_common_qualifier(intent: ToolIntent, *, status_label: str | None = None) -> str:
    qualifier_parts: list[str] = []
    if status_label:
        qualifier_parts.append(status_label)
    if intent.company_name:
        qualifier_parts.append(f"của công ty {intent.company_name}")
    if intent.target_date:
        qualifier_parts.append(f"ngày {intent.target_date:%d/%m/%Y}")
    elif intent.today_only:
        qualifier_parts.append("hôm nay")
    return " ".join(part for part in qualifier_parts if part)


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


def execute_internal_tool(*, user, intent: ToolIntent, profile: str) -> str | None:
    if profile == Conversation.PROFILE_CUSTOMER and intent.tool_name not in PUBLIC_TOOL_NAMES:
        return None

    if intent.tool_name == "public_service_count":
        return _render_count_answer(
            label="dịch vụ công khai",
            count=CheckupCategory.objects.filter(is_active=True, group_checkup__is_active=True).count(),
        )

    if intent.tool_name == "public_package_count":
        return _render_count_answer(
            label="gói khám công khai",
            count=CheckupPackageTemplate.objects.filter(is_active=True).count(),
        )

    if intent.tool_name == "public_doctor_schedule_count":
        return _render_count_answer(
            label="lịch bác sĩ công khai",
            count=DoctorSchedule.objects.count(),
        )

    if intent.tool_name == "employees_count":
        count = count_employees_for_user(user)
        return None if count is None else _render_count_answer(label="nhân viên", count=count)

    if intent.tool_name == "companies_count":
        count = count_companies_for_user(user)
        return None if count is None else _render_count_answer(label="công ty", count=count)

    if intent.tool_name == "patients_count":
        count = count_patients_for_user(user)
        return None if count is None else _render_count_answer(label="bệnh nhân", count=count)

    if intent.tool_name == "individual_bookings_count":
        return _render_count_answer(
            label="yêu cầu đặt khám khách lẻ",
            count=IndividualBooking.objects.count(),
        )

    if intent.tool_name == "schedule_slots_count":
        return _render_count_answer(label="slot lịch", count=ScheduleSlot.objects.count())

    if intent.tool_name == "schedule_configs_count":
        return _render_count_answer(
            label="cấu hình lịch doanh nghiệp",
            count=ContractScheduleConfig.objects.count(),
        )

    if intent.tool_name == "overdue_record_completions":
        rows = list_overdue_record_completion_summaries_for_user(
            user,
            company_name=intent.company_name,
            limit=intent.limit,
        )
        return None if rows is None else _render_overdue_completion_list(rows)

    if intent.tool_name == "appointments":
        if intent.operation == "list":
            rows = list_appointment_summaries_for_user(
                user,
                status=intent.status,
                today_only=intent.today_only,
                target_date=intent.target_date,
                limit=intent.limit,
            )
            return None if rows is None else _render_appointment_list(rows)
        count = count_appointments_for_user(
            user,
            status=intent.status,
            today_only=intent.today_only,
            target_date=intent.target_date,
        )
        return None if count is None else _render_count_answer(
            label="lịch hẹn",
            count=count,
            qualifier=_build_common_qualifier(
                intent,
                status_label=_format_appointment_status(intent.status) if intent.status else None,
            ),
        )

    if intent.tool_name == "checkins":
        if intent.operation == "top":
            rows = list_top_checkin_companies_for_user(
                user,
                status=intent.status,
                today_only=intent.today_only,
                target_date=intent.target_date,
                limit=intent.limit,
            )
            return None if rows is None else _render_top_companies_answer(
                "Top công ty theo số lượng check-in:",
                rows,
            )
        if intent.operation == "list":
            rows = list_checkin_summaries_for_user(
                user,
                status=intent.status,
                today_only=intent.today_only,
                target_date=intent.target_date,
                company_name=intent.company_name,
                limit=intent.limit,
            )
            return None if rows is None else _render_checkin_list(rows)
        count = count_checkins_for_user(
            user,
            status=intent.status,
            today_only=intent.today_only,
            target_date=intent.target_date,
            company_name=intent.company_name,
        )
        return None if count is None else _render_count_answer(
            label="check-in",
            count=count,
            qualifier=_build_common_qualifier(
                intent,
                status_label=_format_checkin_status(intent.status) if intent.status else None,
            ),
        )

    if intent.tool_name == "quotations":
        if intent.operation == "top":
            rows = list_top_quotation_companies_for_user(
                user,
                status=intent.status,
                created_today=intent.today_only,
                target_date=intent.target_date,
                limit=intent.limit,
            )
            return None if rows is None else _render_top_companies_answer(
                "Top công ty theo số lượng báo giá:",
                rows,
            )
        if intent.operation == "list":
            rows = list_quotation_summaries_for_user(
                user,
                status=intent.status,
                created_today=intent.today_only,
                target_date=intent.target_date,
                company_name=intent.company_name,
                limit=intent.limit,
            )
            return None if rows is None else _render_quotation_list(rows)
        count = count_quotations_for_user(
            user,
            status=intent.status,
            created_today=intent.today_only,
            target_date=intent.target_date,
            company_name=intent.company_name,
        )
        return None if count is None else _render_count_answer(
            label="báo giá",
            count=count,
            qualifier=_build_common_qualifier(
                intent,
                status_label=_format_quotation_status(intent.status) if intent.status else None,
            ),
        )

    if intent.tool_name == "contracts":
        if intent.operation == "top":
            rows = list_top_contract_companies_for_user(
                user,
                status=intent.status,
                created_today=intent.today_only,
                target_date=intent.target_date,
                active_only=intent.active_only,
                limit=intent.limit,
            )
            return None if rows is None else _render_top_companies_answer(
                "Top công ty theo số lượng hợp đồng:",
                rows,
            )
        if intent.operation == "list":
            rows = list_contract_summaries_for_user(
                user,
                status=intent.status,
                created_today=intent.today_only,
                target_date=intent.target_date,
                active_only=intent.active_only,
                company_name=intent.company_name,
                limit=intent.limit,
            )
            return None if rows is None else _render_contract_list(rows)
        status_label = "đang hiệu lực" if intent.active_only else (
            _format_contract_status(intent.status) if intent.status else None
        )
        count = count_contracts_for_user(
            user,
            status=intent.status,
            created_today=intent.today_only,
            target_date=intent.target_date,
            active_only=intent.active_only,
            company_name=intent.company_name,
        )
        return None if count is None else _render_count_answer(
            label="hợp đồng",
            count=count,
            qualifier=_build_common_qualifier(intent, status_label=status_label),
        )

    return None
