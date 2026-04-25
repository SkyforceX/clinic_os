from __future__ import annotations

from typing import Iterable

from apps.catalogs.models import CheckupCategory, CheckupPackageTemplate
from apps.catalogs.policies import CatalogPolicy
from apps.procedures.models import Procedure
from apps.procedures.policies import can_view_procedures

from .models import KnowledgeChunk, KnowledgeDocument


def list_published_procedures_for_knowledge() -> Iterable[Procedure]:
    return (
        Procedure.objects.filter(status="published")
        .prefetch_related("steps", "steps__attachments")
        .order_by("pk")
    )


def list_active_checkup_categories_for_knowledge() -> Iterable[CheckupCategory]:
    return (
        CheckupCategory.objects.filter(is_active=True, group_checkup__is_active=True)
        .select_related("group_checkup")
        .order_by("group_checkup__display_order", "display_order", "pk")
    )


def list_active_checkup_packages_for_knowledge() -> Iterable[CheckupPackageTemplate]:
    return (
        CheckupPackageTemplate.objects.filter(is_active=True)
        .select_related("created_by", "updated_by")
        .prefetch_related("items", "items__category", "items__category__group_checkup")
        .order_by("pk")
    )


def list_active_knowledge_chunks(source_types: list[str] | None = None):
    chunks = (
        KnowledgeChunk.records.with_embeddings()
        .select_related("document")
        .filter(document__is_active=True)
    )
    if source_types:
        chunks = chunks.filter(document__source_type__in=source_types)
    return chunks


def list_allowed_knowledge_source_types_for_user(user) -> list[str]:
    source_types = []

    if can_view_procedures(user):
        source_types.append(KnowledgeDocument.SOURCE_PROCEDURE)

    if CatalogPolicy.can_view_categories(user):
        source_types.append(KnowledgeDocument.SOURCE_CATEGORY)

    if CatalogPolicy.can_view_packages(user):
        source_types.append(KnowledgeDocument.SOURCE_PACKAGE)

    return source_types
