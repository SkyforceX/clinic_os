from __future__ import annotations

from apps.ai_assistant.models import Message


def list_conversation_messages(conversation, *, include_system: bool = False):
    queryset = conversation.messages.order_by("created_at")
    if not include_system:
        queryset = queryset.exclude(role=Message.ROLE_SYSTEM)
    return queryset
