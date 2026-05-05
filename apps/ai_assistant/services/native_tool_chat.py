from __future__ import annotations

import json
import logging

from django.conf import settings

from .internal_tool_runtime import execute_internal_tool, normalize_text
from .llm_client import (
    complete_openai_chat_message,
    complete_openai_chat_with_tools,
    get_toolcall_candidate_models,
    get_toolcall_final_timeout,
    get_toolcall_timeout,
)
from .nlu_planner import (
    extract_native_tool_payload,
    get_native_planning_messages,
    get_native_planning_tool_choice,
    get_native_planning_tools,
    plan_tool_call,
    parse_tool_payload,
)
from .telemetry import emit_ai_tool_event


logger = logging.getLogger(__name__)


def _looks_like_data_query(question: str) -> bool:
    normalized = normalize_text(question)
    return any(
        token in normalized
        for token in (
            "bao nhieu",
            "so luong",
            "tong so",
            "liet ke",
            "danh sach",
            "top",
            "nhieu nhat",
            "dang ky kham",
            "lich hen",
            "bao gia",
            "hop dong",
            "checkin",
            "check in",
            "benh nhan",
            "nhan vien",
            "cong ty",
            "ho so",
        )
    )


def _tool_result_payload(*, tool_name: str, result_text: str) -> str:
    return json.dumps(
        {
            "ok": True,
            "tool_name": tool_name,
            "result_text": result_text,
        },
        ensure_ascii=False,
    )


def _run_structured_planner_fallback(*, user, question: str, profile: str, reason: str) -> str | None:
    logger.info("Native tool chat falling back to structured planner: %s", reason)
    emit_ai_tool_event("native_tool_structured_fallback", profile=profile, reason=reason)
    planned = plan_tool_call(
        user=user,
        question=question,
        profile=profile,
        allow_native=False,
    )
    if planned.clarification_question:
        return planned.clarification_question
    if planned.intent is None:
        return None
    return execute_internal_tool(user=user, intent=planned.intent, profile=profile)


def run_native_tool_chat_reply(
    *,
    user,
    question: str,
    profile: str,
    messages_payload: list[dict],
) -> str | None:
    if not _looks_like_data_query(question):
        return None

    if not getattr(settings, "AI_TOOLCALL_ENABLED", True):
        logger.info("Native tool chat disabled via AI_TOOLCALL_ENABLED.")
        emit_ai_tool_event("native_tool_disabled", profile=profile)
        return None

    tool_models = get_toolcall_candidate_models()
    planner_timeout = get_toolcall_timeout()
    final_timeout = get_toolcall_final_timeout()
    logger.info(
        "Native tool chat start models=%s planner_timeout=%s final_timeout=%s profile=%s",
        ",".join(tool_models),
        planner_timeout,
        final_timeout,
        profile,
    )
    emit_ai_tool_event(
        "native_tool_start",
        profile=profile,
        candidate_models=tool_models,
        planner_timeout=planner_timeout,
        final_timeout=final_timeout,
    )

    first_message = None
    selected_model = None
    planning_messages = get_native_planning_messages(question=question, profile=profile)
    planning_tools = get_native_planning_tools(profile)
    tool_choice = get_native_planning_tool_choice()
    for tool_model in tool_models:
        first_message = complete_openai_chat_with_tools(
            planning_messages,
            tools=planning_tools,
            model=tool_model,
            temperature=0.1,
            max_tokens=120,
            timeout=planner_timeout,
            tool_choice=tool_choice,
        )
        if first_message:
            selected_model = tool_model
            logger.info("Native tool chat planner succeeded with model=%s", tool_model)
            emit_ai_tool_event("native_tool_planner_success", profile=profile, model=tool_model)
            break
        logger.info("Native tool chat planner returned no message for model=%s; trying next candidate.", tool_model)
        emit_ai_tool_event("native_tool_planner_retry", profile=profile, model=tool_model)
    if not first_message:
        return _run_structured_planner_fallback(
            user=user,
            question=question,
            profile=profile,
            reason="planner_no_message",
        )
    tool_model = selected_model or tool_models[0]

    payload = extract_native_tool_payload(first_message)
    if not payload:
        return _run_structured_planner_fallback(
            user=user,
            question=question,
            profile=profile,
            reason="planner_no_payload",
        )

    planned = parse_tool_payload(
        user=user,
        question=question,
        profile=profile,
        payload={"action": "tool_call", **payload},
    )
    if planned.intent is None:
        if planned.clarification_question:
            logger.info("Native tool chat planner requested clarification.")
            emit_ai_tool_event("native_tool_clarify", profile=profile, model=tool_model)
            return planned.clarification_question
        return _run_structured_planner_fallback(
            user=user,
            question=question,
            profile=profile,
            reason="intent_parse_failed",
        )

    result_text = execute_internal_tool(
        user=user,
        intent=planned.intent,
        profile=profile,
    )
    if result_text is None:
        return _run_structured_planner_fallback(
            user=user,
            question=question,
            profile=profile,
            reason="executor_no_result",
        )
    logger.info("Native tool chat executed tool=%s operation=%s", planned.intent.tool_name, planned.intent.operation)
    emit_ai_tool_event(
        "native_tool_executed",
        profile=profile,
        model=tool_model,
        tool_name=planned.intent.tool_name,
        operation=planned.intent.operation,
    )

    tool_calls = first_message.get("tool_calls") or []
    if not tool_calls:
        logger.info("Native tool chat no tool_calls array after execution; using raw tool result.")
        emit_ai_tool_event(
            "native_tool_raw_result",
            profile=profile,
            model=tool_model,
            tool_name=planned.intent.tool_name,
            operation=planned.intent.operation,
            reason="missing_tool_calls_array",
        )
        return result_text

    tool_call_id = (tool_calls[0] or {}).get("id")
    round_trip_messages = list(messages_payload)
    round_trip_messages.append(
        {
            "role": "assistant",
            "content": (first_message.get("content") or "").strip(),
            "tool_calls": tool_calls,
        }
    )
    round_trip_messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": _tool_result_payload(
                tool_name=planned.intent.tool_name,
                result_text=result_text,
            ),
        }
    )

    final_choice = complete_openai_chat_message(
        round_trip_messages,
        model=tool_model,
        temperature=0.2,
        max_tokens=260,
        timeout=final_timeout,
    )
    if not final_choice:
        logger.info("Native tool chat final assistant step failed; returning raw tool result.")
        emit_ai_tool_event(
            "native_tool_raw_result",
            profile=profile,
            model=tool_model,
            tool_name=planned.intent.tool_name,
            operation=planned.intent.operation,
            reason="final_step_failed",
        )
        return result_text

    final_message = final_choice.get("message") or {}
    final_content = (final_message.get("content") or "").strip()
    if final_content:
        logger.info("Native tool chat final assistant reply generated successfully.")
        emit_ai_tool_event(
            "native_tool_success",
            profile=profile,
            model=tool_model,
            tool_name=planned.intent.tool_name,
            operation=planned.intent.operation,
        )
        return final_content

    logger.warning("Native tool final reply empty, fallback to raw tool result.")
    emit_ai_tool_event(
        "native_tool_raw_result",
        profile=profile,
        model=tool_model,
        tool_name=planned.intent.tool_name,
        operation=planned.intent.operation,
        reason="final_reply_empty",
    )
    return result_text
