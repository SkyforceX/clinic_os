from __future__ import annotations

from apps.ai_knowledge.models import AIKnowledgeChunk


def list_indexed_chunks(
    *,
    source_types: list[str] | None = None,
    locale: str | None = None,
    access_levels: list[str] | None = None,
):
    queryset = AIKnowledgeChunk.objects.filter(
        status="indexed",
        source_record__status="indexed",
        embedding__isnull=False,
    ).select_related("source_record")
    if source_types:
        queryset = queryset.filter(source_type__in=source_types)
    if locale:
        queryset = queryset.filter(locale=locale)
    if access_levels:
        queryset = queryset.filter(access_level__in=access_levels)
    return queryset.order_by("source_id", "section_key", "chunk_index")


def get_neighbor_chunks(
    *,
    source_id: str,
    source_type: str,
    section_key: str,
    chunk_index: int,
    radius: int = 1,
    locale: str | None = None,
    access_levels: list[str] | None = None,
):
    queryset = AIKnowledgeChunk.objects.filter(
        source_id=str(source_id),
        source_type=source_type,
        section_key=section_key,
        status="indexed",
    ).select_related("source_record")
    if locale:
        queryset = queryset.filter(locale=locale)
    if access_levels:
        queryset = queryset.filter(access_level__in=access_levels)
    return queryset.filter(
        chunk_index__gte=max(chunk_index - radius, 0),
        chunk_index__lte=chunk_index + radius,
    ).order_by("chunk_index")
