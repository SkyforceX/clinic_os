from __future__ import annotations

from apps.ai_knowledge.models import AIKnowledgeSource


def list_sources(*, source_types: list[str] | None = None, status: str | None = None):
    queryset = AIKnowledgeSource.objects.all().order_by("source_type", "source_id")
    if source_types:
        queryset = queryset.filter(source_type__in=source_types)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def get_source(*, source_type: str, source_id: str) -> AIKnowledgeSource | None:
    return (
        AIKnowledgeSource.objects.filter(
            source_type=source_type,
            source_id=str(source_id),
        )
        .order_by("pk")
        .first()
    )
