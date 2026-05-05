from __future__ import annotations

from apps.ai_assistant.selectors import list_conversation_messages


def load_conversation_messages(conversation):
    return list_conversation_messages(conversation)
