from __future__ import annotations

from apps.ai_assistant.models import Conversation


def list_conversations_for_user(user, *, profile: str | None = None, limit: int | None = None):
    queryset = Conversation.objects.filter(user=user).order_by("-updated_at")
    if profile:
        queryset = queryset.filter(profile=profile)
    if limit is not None:
        return queryset[:limit]
    return queryset


def get_conversation_for_user(*, pk: int, user, profile: str | None = None) -> Conversation | None:
    queryset = Conversation.objects.filter(pk=pk, user=user).order_by("pk")
    if profile:
        queryset = queryset.filter(profile=profile)
    return queryset.first()


def list_conversations_for_session(*, session_key: str, profile: str, limit: int | None = None):
    queryset = Conversation.objects.filter(
        session_key=session_key,
        profile=profile,
    ).order_by("-updated_at")
    if limit is not None:
        return queryset[:limit]
    return queryset


def get_conversation_for_session(*, pk: int, session_key: str, profile: str) -> Conversation | None:
    return (
        Conversation.objects.filter(
            pk=pk,
            session_key=session_key,
            profile=profile,
        )
        .order_by("pk")
        .first()
    )
