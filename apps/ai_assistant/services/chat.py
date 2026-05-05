from __future__ import annotations

import json
import logging

from django.utils import timezone

from apps.ai_assistant.models import Conversation, Message
from apps.ai_assistant.selectors import list_conversation_messages

from .assistant_runtime import build_knowledge_context
from .conversation_state import build_conversation_state
from .intent_router import route_pre_llm_action
from .native_tool_chat import run_native_tool_chat_reply
from .llm_client import auto_generate_title, stream_completion
from .prompting import build_messages_payload, get_guardrail_response


logger = logging.getLogger(__name__)


def create_conversation(*, user=None, profile: str, session_key: str = "") -> Conversation:
    return Conversation.objects.create(
        user=user,
        profile=profile,
        session_key=session_key,
        title="",
    )


def stream_conversation_reply(*, conversation: Conversation, user, user_content: str):
    user_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=user_content,
    )

    guardrail_response = get_guardrail_response(user_content)
    if guardrail_response:
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content=guardrail_response,
        )
        Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
        yield f"data: {json.dumps(guardrail_response)}\n\n"
        yield "data: [DONE]\n\n"
        return

    pre_llm_response = route_pre_llm_action(
        conversation=conversation,
        user=user,
        question=user_content,
        profile=conversation.profile,
    )
    if pre_llm_response:
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content=pre_llm_response,
        )
        Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
        yield f"data: {json.dumps(pre_llm_response)}\n\n"
        yield "data: [DONE]\n\n"
        return

    is_first_message = conversation.messages.filter(role=Message.ROLE_USER).count() == 1
    all_messages = list_conversation_messages(conversation)
    conversation_state = build_conversation_state(all_messages)

    knowledge_context = ""
    try:
        knowledge_context = build_knowledge_context(
            user_content,
            user=user,
            profile=conversation.profile,
        )
    except Exception as exc:
        logger.exception("AI knowledge context setup failed: %s", exc)

    messages_payload = build_messages_payload(
        all_messages,
        knowledge_context=knowledge_context,
        profile=conversation.profile,
        conversation_state=conversation_state,
    )
    full_response_parts: list[str] = []

    try:
        native_tool_response = run_native_tool_chat_reply(
            user=user,
            question=user_content,
            profile=conversation.profile,
            messages_payload=messages_payload,
        )
        if native_tool_response:
            assistant_content = native_tool_response.strip()
            if assistant_content:
                Message.objects.create(
                    conversation=conversation,
                    role=Message.ROLE_ASSISTANT,
                    content=assistant_content,
                )
                Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
                if is_first_message and not conversation.title:
                    title = auto_generate_title(user_content)
                    if title:
                        Conversation.objects.filter(pk=conversation.pk).update(title=title)
                yield f"data: {json.dumps(assistant_content)}\n\n"
                yield "data: [DONE]\n\n"
                return

        for chunk in stream_completion(messages_payload):
            full_response_parts.append(chunk)
            yield f"data: {json.dumps(chunk)}\n\n"

        assistant_content = "".join(full_response_parts).strip()
        if assistant_content:
            Message.objects.create(
                conversation=conversation,
                role=Message.ROLE_ASSISTANT,
                content=assistant_content,
            )

        Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
        if is_first_message and not conversation.title:
            title = auto_generate_title(user_content)
            if title:
                Conversation.objects.filter(pk=conversation.pk).update(title=title)
        yield "data: [DONE]\n\n"

    except RuntimeError as exc:
        logger.warning("AI stream RuntimeError: %s", exc)
        user_msg.delete()
        yield f"data: [ERROR] {json.dumps(str(exc))}\n\n"
    except Exception as exc:
        logger.exception("AI stream unexpected error: %s", exc)
        user_msg.delete()
        yield f"data: [ERROR] {json.dumps('Đã xảy ra lỗi không xác định.')}\n\n"
