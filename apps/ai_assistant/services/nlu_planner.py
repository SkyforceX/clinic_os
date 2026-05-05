from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from apps.ai_assistant.models import Conversation
from apps.booking.models import AppointmentStatus
from apps.contract.models import ContractStatus
from apps.contract.models.quotation import QuotationStatus
from apps.reception.models import CheckInStatus

from .internal_tool_runtime import (
    ToolIntent,
    execute_internal_tool,
    extract_company_name,
    normalize_text,
    parse_iso_or_local_date,
)
from .llm_client import (
    complete_openai_chat_with_tools,
    complete_sync,
    get_toolcall_candidate_models,
    get_toolcall_timeout,
)
from .telemetry import emit_ai_tool_event


logger = logging.getLogger(__name__)

COUNT_PATTERNS = ("bao nhieu", "co may", "so luong", "tong so", "dem", "thong ke")
LIST_PATTERNS = ("liet ke", "danh sach", "show")
ATTENTION_PATTERNS = ("qua han", "can chu y", "cho xu ly")
TOP_PATTERNS = ("top", "nhieu nhat")
TOOL_HINT_PATTERNS = (
    "bao gia",
    "hop dong",
    "lich hen",
    "dang ky kham",
    "check in",
    "checkin",
    "benh nhan",
    "nhan vien",
    "cong ty",
    "ho so",
    "bac si",
    "goi kham",
    "dich vu",
    "booking",
    "slot",
    "lich kham",
)


@dataclass(frozen=True)
class PlannedToolCall:
    intent: ToolIntent | None = None
    clarification_question: str | None = None


def _looks_like_tool_query(normalized_question: str) -> bool:
    if any(pattern in normalized_question for pattern in TOOL_HINT_PATTERNS):
        return True
    return any(
        pattern in normalized_question
        for pattern in (*COUNT_PATTERNS, *LIST_PATTERNS, *ATTENTION_PATTERNS, *TOP_PATTERNS)
    )


def _extract_json_object(raw_text: str) -> dict | None:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _default_operation(normalized_question: str) -> str:
    if any(pattern in normalized_question for pattern in TOP_PATTERNS):
        return "top"
    if any(pattern in normalized_question for pattern in LIST_PATTERNS):
        return "list"
    if any(pattern in normalized_question for pattern in ATTENTION_PATTERNS):
        return "attention"
    return "count"


def _normalize_operation(value: str | None, normalized_question: str) -> str:
    normalized = normalize_text(value or "")
    mapping = {
        "count": "count",
        "dem": "count",
        "so luong": "count",
        "tong so": "count",
        "list": "list",
        "liet ke": "list",
        "danh sach": "list",
        "top": "top",
        "nhieu nhat": "top",
        "attention": "attention",
        "can chu y": "attention",
        "qua han": "attention",
    }
    return mapping.get(normalized, _default_operation(normalized_question))


def _infer_tool_name(normalized_question: str, profile: str) -> str | None:
    if profile == Conversation.PROFILE_CUSTOMER:
        if "dich vu" in normalized_question:
            return "public_service_count"
        if "goi kham" in normalized_question:
            return "public_package_count"
        if "bac si" in normalized_question or "lich kham" in normalized_question:
            return "public_doctor_schedule_count"
        return None

    mapping = (
        ("appointments", ("dang ky kham", "lich hen", "lich kham", "ca kham", "booking")),
        ("checkins", ("check in", "checkin", "tiep don")),
        ("quotations", ("bao gia", "quotation", "quote")),
        ("contracts", ("hop dong", "contract")),
        ("companies_count", ("cong ty", "doanh nghiep")),
        ("patients_count", ("benh nhan", "khach hang")),
        ("employees_count", ("nhan vien", "employee")),
        ("overdue_record_completions", ("ho so", "qua han", "can chu y")),
        ("individual_bookings_count", ("dang ky ca nhan", "booking ca nhan")),
        ("schedule_slots_count", ("slot", "khung gio")),
        ("schedule_configs_count", ("cau hinh lich", "lich cau hinh")),
    )
    for tool_name, patterns in mapping:
        if any(pattern in normalized_question for pattern in patterns):
            return tool_name
    return None


def _normalize_tool_name(tool_name: str, profile: str) -> str | None:
    allowed = {
        "appointments",
        "checkins",
        "quotations",
        "contracts",
        "companies_count",
        "patients_count",
        "employees_count",
        "overdue_record_completions",
        "individual_bookings_count",
        "schedule_slots_count",
        "schedule_configs_count",
        "public_service_count",
        "public_package_count",
        "public_doctor_schedule_count",
    }
    normalized = normalize_text(tool_name)
    aliases = {
        "appointment": "appointments",
        "appointments": "appointments",
        "booking": "appointments",
        "bookings": "appointments",
        "dang ky kham": "appointments",
        "lich hen": "appointments",
        "lich kham": "appointments",
        "ca kham": "appointments",
        "check in": "checkins",
        "checkin": "checkins",
        "checkins": "checkins",
        "quotation": "quotations",
        "quotations": "quotations",
        "bao gia": "quotations",
        "quote": "quotations",
        "contract": "contracts",
        "contracts": "contracts",
        "hop dong": "contracts",
        "company": "companies_count",
        "companies": "companies_count",
        "cong ty": "companies_count",
        "patient": "patients_count",
        "patients": "patients_count",
        "benh nhan": "patients_count",
        "employee": "employees_count",
        "employees": "employees_count",
        "nhan vien": "employees_count",
        "overdue record completions": "overdue_record_completions",
        "overdue_record_completions": "overdue_record_completions",
        "ho so qua han": "overdue_record_completions",
        "individual bookings": "individual_bookings_count",
        "individual_bookings_count": "individual_bookings_count",
        "schedule slots": "schedule_slots_count",
        "schedule_slots_count": "schedule_slots_count",
        "slot": "schedule_slots_count",
        "schedule configs": "schedule_configs_count",
        "schedule_configs_count": "schedule_configs_count",
        "public service count": "public_service_count",
        "public_service_count": "public_service_count",
        "public package count": "public_package_count",
        "public_package_count": "public_package_count",
        "public doctor schedule count": "public_doctor_schedule_count",
        "public_doctor_schedule_count": "public_doctor_schedule_count",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in allowed:
        if profile == Conversation.PROFILE_CUSTOMER and not normalized.startswith("public_"):
            return None
        return normalized
    return None


def _normalize_appointment_status(value: str | None) -> str | None:
    normalized = normalize_text(value or "")
    mapping = {
        "pending": AppointmentStatus.PENDING,
        "cho xac nhan": AppointmentStatus.PENDING,
        "confirmed": AppointmentStatus.CONFIRMED,
        "da xac nhan": AppointmentStatus.CONFIRMED,
        "checked_in": AppointmentStatus.CHECKED_IN,
        "check in": AppointmentStatus.CHECKED_IN,
        "in_progress": AppointmentStatus.IN_PROGRESS,
        "dang kham": AppointmentStatus.IN_PROGRESS,
        "completed": AppointmentStatus.COMPLETED,
        "hoan thanh": AppointmentStatus.COMPLETED,
        "cancelled": AppointmentStatus.CANCELLED,
        "huy": AppointmentStatus.CANCELLED,
        "no_show": AppointmentStatus.NO_SHOW,
        "vang": AppointmentStatus.NO_SHOW,
    }
    return mapping.get(normalized)


def _normalize_checkin_status(value: str | None) -> str | None:
    normalized = normalize_text(value or "")
    mapping = {
        "checked_in": CheckInStatus.CHECKED_IN,
        "check in": CheckInStatus.CHECKED_IN,
        "checked_out": CheckInStatus.CHECKED_OUT,
        "check out": CheckInStatus.CHECKED_OUT,
        "deferred": CheckInStatus.DEFERRED,
        "quay lai sau": CheckInStatus.DEFERRED,
    }
    return mapping.get(normalized)


def _normalize_quotation_status(value: str | None) -> str | None:
    normalized = normalize_text(value or "")
    mapping = {
        "draft": QuotationStatus.DRAFT,
        "nhap": QuotationStatus.DRAFT,
        "submitted": QuotationStatus.SUBMITTED,
        "cho duyet": QuotationStatus.SUBMITTED,
        "approved": QuotationStatus.APPROVED,
        "da duyet": QuotationStatus.APPROVED,
        "rejected": QuotationStatus.REJECTED,
        "tu choi": QuotationStatus.REJECTED,
    }
    return mapping.get(normalized)


def _normalize_contract_status(value: str | None) -> str | None:
    normalized = normalize_text(value or "")
    mapping = {
        "draft": ContractStatus.DRAFT,
        "nhap": ContractStatus.DRAFT,
        "submitted": ContractStatus.SUBMITTED,
        "cho duyet": ContractStatus.SUBMITTED,
        "approved": ContractStatus.APPROVED,
        "da duyet": ContractStatus.APPROVED,
        "active": ContractStatus.ACTIVE,
        "dang hieu luc": ContractStatus.ACTIVE,
        "finished": ContractStatus.FINISHED,
        "hoan tat": ContractStatus.FINISHED,
        "terminated": ContractStatus.TERMINATED,
        "cham dut": ContractStatus.TERMINATED,
        "cancelled": ContractStatus.CANCELLED,
        "huy": ContractStatus.CANCELLED,
    }
    return mapping.get(normalized)


def _normalize_status(tool_name: str, value: str | None) -> str | None:
    if tool_name == "appointments":
        return _normalize_appointment_status(value)
    if tool_name == "checkins":
        return _normalize_checkin_status(value)
    if tool_name == "quotations":
        return _normalize_quotation_status(value)
    if tool_name == "contracts":
        return _normalize_contract_status(value)
    return None


def _build_nlu_messages(*, question: str, profile: str) -> list[dict]:
    today = timezone.localdate()
    return [
        {
            "role": "system",
            "content": (
                "Ban la bo dinh tuyen y dinh cho chatbot Clinic OS. "
                "Neu cau hoi la truy van du lieu van hanh, hay goi dung function duoc cung cap. "
                "Neu cau hoi khong phai truy van du lieu hoac ban khong du chac chan, khong goi function."
            ),
        },
        {
            "role": "system",
            "content": (
                "Ngay hien tai la "
                f"{today:%Y-%m-%d}. "
                "Neu co ngay cu the trong cau hoi thi map vao target_date theo YYYY-MM-DD. "
                "Neu nguoi dung hoi hom nay thi today_only=true. "
                "Neu cau hoi ve ho so qua han can chu y thi chon overdue_record_completions voi operation=attention. "
                "Neu profile la customer thi chi duoc chon tool public_*. "
                "Neu khong can tool, hay tra loi mot cau ngan de hoi lam ro."
            ),
        },
        {
            "role": "system",
            "content": f"Assistant profile: {profile}",
        },
        {"role": "user", "content": question},
    ]


def _planning_tool_definitions(profile: str) -> list[dict]:
    tool_name_enum = [
        "appointments",
        "checkins",
        "quotations",
        "contracts",
        "companies_count",
        "patients_count",
        "employees_count",
        "overdue_record_completions",
        "individual_bookings_count",
        "schedule_slots_count",
        "schedule_configs_count",
        "public_service_count",
        "public_package_count",
        "public_doctor_schedule_count",
    ]
    if profile == Conversation.PROFILE_CUSTOMER:
        tool_name_enum = [
            "public_service_count",
            "public_package_count",
            "public_doctor_schedule_count",
        ]

    return [
        {
            "type": "function",
            "function": {
                "name": "clinicos_data_query",
                "description": (
                    "Chon truy van du lieu noi bo phu hop cho cau hoi nguoi dung. "
                    "Chi goi function nay khi can dem, liet ke, top, hoac can chu y theo du lieu he thong."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "enum": tool_name_enum,
                        },
                        "operation": {
                            "type": "string",
                            "enum": ["count", "list", "top", "attention"],
                        },
                        "status": {
                            "type": ["string", "null"],
                            "description": "Trang thai raw neu co, vi du CONFIRMED, da xac nhan, cho duyet.",
                        },
                        "company_name": {
                            "type": ["string", "null"],
                        },
                        "target_date": {
                            "type": ["string", "null"],
                            "description": "Ngay theo dinh dang YYYY-MM-DD neu cau hoi nhac ngay cu the.",
                        },
                        "today_only": {"type": "boolean"},
                        "active_only": {"type": "boolean"},
                        "limit": {
                            "type": ["integer", "null"],
                            "minimum": 1,
                            "maximum": 10,
                        },
                    },
                    "required": ["tool_name", "operation", "today_only", "active_only"],
                },
            },
        }
    ]


def get_native_planning_tools(profile: str) -> list[dict]:
    return _planning_tool_definitions(profile)


def get_native_planning_messages(*, question: str, profile: str) -> list[dict]:
    return _build_nlu_messages(question=question, profile=profile)


def get_native_planning_tool_choice() -> dict:
    return {
        "type": "function",
        "function": {"name": "clinicos_data_query"},
    }


def _extract_native_tool_payload(message: dict | None) -> dict | None:
    if not message:
        return None
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None
    first_call = tool_calls[0] or {}
    function_payload = first_call.get("function") or {}
    if function_payload.get("name") != "clinicos_data_query":
        return None
    arguments = function_payload.get("arguments")
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        return _extract_json_object(arguments)
    return None


def extract_native_tool_payload(message: dict | None) -> dict | None:
    return _extract_native_tool_payload(message)


def _plan_tool_call_native(*, question: str, profile: str) -> tuple[dict | None, str | None]:
    if not getattr(settings, "AI_TOOLCALL_ENABLED", True):
        logger.info("Native planner disabled via AI_TOOLCALL_ENABLED.")
        emit_ai_tool_event("native_planner_disabled", profile=profile)
        return None, None
    messages = _build_nlu_messages(question=question, profile=profile)
    timeout = get_toolcall_timeout()
    tools = _planning_tool_definitions(profile)
    tool_choice = get_native_planning_tool_choice()
    for model in get_toolcall_candidate_models():
        logger.info("Native planner requesting tool call with model=%s timeout=%s profile=%s", model, timeout, profile)
        emit_ai_tool_event("native_planner_attempt", profile=profile, model=model, timeout=timeout)
        message = complete_openai_chat_with_tools(
            messages,
            tools=tools,
            model=model,
            temperature=0.1,
            max_tokens=120,
            timeout=timeout,
            tool_choice=tool_choice,
        )
        if not message:
            logger.info("Native planner returned no message for model=%s; trying next candidate.", model)
            emit_ai_tool_event("native_planner_retry", profile=profile, model=model, reason="no_message")
            continue
        payload = _extract_native_tool_payload(message)
        content = (message.get("content") or "").strip()
        if payload:
            logger.info("Native planner produced tool payload for profile=%s model=%s", profile, model)
            emit_ai_tool_event("native_planner_success", profile=profile, model=model)
            return payload, content or None
        if content:
            logger.info("Native planner returned assistant content instead of tool payload for model=%s", model)
            emit_ai_tool_event("native_planner_content_only", profile=profile, model=model)
            return None, content
        logger.info("Native planner returned empty payload/content for model=%s", model)
        emit_ai_tool_event("native_planner_retry", profile=profile, model=model, reason="empty_payload")
    logger.info("Native planner exhausted all candidate models; falling back.")
    emit_ai_tool_event("native_planner_fallback", profile=profile, reason="all_candidates_exhausted")
    return None, None


def _parse_planned_tool_call(*, user, question: str, profile: str, payload: dict | None) -> PlannedToolCall:
    normalized_question = normalize_text(question)
    if not payload:
        return PlannedToolCall()

    action = str(payload.get("action") or "tool_call").strip().lower()
    if action == "ask_clarify":
        clarification = (payload.get("clarification_question") or "").strip()
        if clarification:
            return PlannedToolCall(clarification_question=clarification)
        return PlannedToolCall(clarification_question="Ban co the noi ro hon yeu cau can tra cuu khong?")

    if action != "tool_call":
        return PlannedToolCall()

    tool_name = _normalize_tool_name(str(payload.get("tool_name") or "").strip(), profile)
    if not tool_name:
        tool_name = _infer_tool_name(normalized_question, profile)
    if not tool_name:
        return PlannedToolCall()

    operation = _normalize_operation(payload.get("operation"), normalized_question)

    limit = payload.get("limit")
    try:
        limit = int(limit) if limit is not None else 5
    except (TypeError, ValueError):
        limit = 5
    limit = min(max(limit, 1), 10)

    target_date = parse_iso_or_local_date(payload.get("target_date"))
    today_only = bool(payload.get("today_only")) and target_date is None
    company_name = extract_company_name(
        user,
        normalized_question,
        preferred_name=(payload.get("company_name") or "").strip() or None,
    )
    active_only = bool(payload.get("active_only"))
    status = _normalize_status(tool_name, payload.get("status"))

    if tool_name == "overdue_record_completions":
        operation = "attention"
    if tool_name.endswith("_count"):
        operation = "count"

    return PlannedToolCall(
        intent=ToolIntent(
            tool_name=tool_name,
            operation=operation,
            status=status,
            company_name=company_name,
            target_date=target_date,
            today_only=today_only,
            active_only=active_only,
            limit=limit,
        )
    )


def parse_tool_payload(*, user, question: str, profile: str, payload: dict | None) -> PlannedToolCall:
    return _parse_planned_tool_call(
        user=user,
        question=question,
        profile=profile,
        payload=payload,
    )


def _plan_tool_call_json_fallback(*, user, question: str, profile: str) -> PlannedToolCall:
    today = timezone.localdate()
    messages = [
        {
            "role": "system",
            "content": (
                "Ban la bo dinh tuyen y dinh cho chatbot Clinic OS. "
                "Chi tra ve JSON hop le, khong giai thich."
            ),
        },
        {
            "role": "system",
            "content": (
                "JSON schema: "
                '{"action":"tool_call|ask_clarify|none","tool_name":"appointments|checkins|quotations|contracts|companies_count|patients_count|employees_count|overdue_record_completions|individual_bookings_count|schedule_slots_count|schedule_configs_count|public_service_count|public_package_count|public_doctor_schedule_count","operation":"count|list|top|attention","status":string|null,"company_name":string|null,"target_date":"YYYY-MM-DD"|null,"today_only":boolean,"active_only":boolean,"limit":number|null,"clarification_question":string|null}. '
                f"Ngay hien tai la {today:%Y-%m-%d}."
            ),
        },
        {
            "role": "system",
            "content": f"Assistant profile: {profile}",
        },
        {"role": "user", "content": question},
    ]
    raw_response = complete_sync(messages, temperature=0.1, max_tokens=220, timeout=8)
    return _parse_planned_tool_call(
        user=user,
        question=question,
        profile=profile,
        payload=_extract_json_object(raw_response),
    )


def plan_tool_call(*, user, question: str, profile: str, allow_native: bool = True) -> PlannedToolCall:
    # Customer profile dùng rule-based routing trực tiếp trong tool_router.
    # NLU planner không cần thiết và gây timeout trên model nhỏ.
    if profile == Conversation.PROFILE_CUSTOMER:
        return PlannedToolCall()

    normalized_question = normalize_text(question)
    if not _looks_like_tool_query(normalized_question):
        return PlannedToolCall()

    native_payload = None
    assistant_content = None
    if allow_native:
        try:
            native_payload, assistant_content = _plan_tool_call_native(
                question=question,
                profile=profile,
            )
        except Exception as exc:
            logger.warning("Native tool planner failed: %s", exc)
            native_payload, assistant_content = None, None

    if native_payload:
        return _parse_planned_tool_call(
            user=user,
            question=question,
            profile=profile,
            payload={"action": "tool_call", **native_payload},
        )

    if assistant_content:
        return PlannedToolCall(clarification_question=assistant_content)

    try:
        return _plan_tool_call_json_fallback(
            user=user,
            question=question,
            profile=profile,
        )
    except Exception as exc:
        logger.warning("Structured JSON planner fallback failed: %s", exc)
        return PlannedToolCall()


def route_structured_tool_call(*, user, question: str, profile: str) -> str | None:
    planned = plan_tool_call(user=user, question=question, profile=profile)
    if planned.clarification_question:
        return planned.clarification_question
    if planned.intent is None:
        return None
    return execute_internal_tool(user=user, intent=planned.intent, profile=profile)
