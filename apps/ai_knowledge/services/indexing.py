from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.ai_knowledge.models import AIKnowledgeChunk, AIKnowledgeSource
from apps.ai_knowledge.selectors.sources import get_source

from .chunking import create_chunks
from .embedding import embed_texts, get_embedding_dimensions, get_embedding_model
from .extractors import (
    SUPPORTED_SOURCE_TYPES,
    SourceDocument,
    extract_text_for_source,
    list_source_documents,
)


logger = logging.getLogger(__name__)


def _resolve_chunking_options(source_type: str) -> dict:
    if source_type in {
        AIKnowledgeSource.SOURCE_CONTRACT,
        AIKnowledgeSource.SOURCE_QUOTATION,
        AIKnowledgeSource.SOURCE_POLICY,
    }:
        return {"max_chars": 1800, "overlap_chars": 250}
    if source_type in {
        AIKnowledgeSource.SOURCE_PATIENT_SUMMARY,
        AIKnowledgeSource.SOURCE_VISIT_SUMMARY,
        AIKnowledgeSource.SOURCE_CLINICAL_NOTE,
        AIKnowledgeSource.SOURCE_MEDICAL_RECORD,
    }:
        return {"max_chars": 900, "overlap_chars": 100}
    return {"max_chars": 1200, "overlap_chars": 160}


def _build_source_defaults(document: SourceDocument) -> dict:
    return {
        "title": document.title,
        "source_url": document.source_url,
        "locale": document.locale,
        "status": AIKnowledgeSource.STATUS_PENDING,
        "content_hash": document.content_hash,
        "last_error": "",
        "access_level": document.access_level,
        "metadata": document.metadata,
    }


def _upsert_source(document: SourceDocument) -> AIKnowledgeSource:
    source = get_source(source_type=document.source_type, source_id=document.source_id)
    defaults = _build_source_defaults(document)
    if source is None:
        return AIKnowledgeSource.objects.create(
            source_type=document.source_type,
            source_id=document.source_id,
            **defaults,
        )

    for field_name, value in defaults.items():
        setattr(source, field_name, value)
    source.save(
        update_fields=[
            "title",
            "source_url",
            "locale",
            "status",
            "content_hash",
            "last_error",
            "access_level",
            "metadata",
            "updated_at",
        ]
    )
    return source


def _write_chunks(source: AIKnowledgeSource, document: SourceDocument) -> int:
    chunk_options = _resolve_chunking_options(document.source_type)
    chunk_payloads = create_chunks(
        document.content,
        title=document.title,
        section_title=document.title,
        section_key=document.metadata.get("section_key", "default"),
        metadata=document.metadata,
        **chunk_options,
    )
    embeddings = embed_texts([chunk.content for chunk in chunk_payloads]) if chunk_payloads else []

    AIKnowledgeChunk.objects.filter(source_record=source).delete()

    chunks_to_create = []
    for payload, embedding in zip(chunk_payloads, embeddings):
        chunks_to_create.append(
            AIKnowledgeChunk(
                source_record=source,
                source_type=source.source_type,
                source_id=source.source_id,
                section_key=payload.section_key,
                chunk_index=payload.chunk_index,
                title=payload.title,
                section_title=payload.section_title,
                content=payload.content,
                embedding=embedding,
                embedding_model=get_embedding_model(),
                embedding_dim=get_embedding_dimensions(),
                token_count=payload.token_count,
                prev_chunk_index=payload.prev_chunk_index,
                next_chunk_index=payload.next_chunk_index,
                access_level=source.access_level,
                locale=source.locale,
                status=AIKnowledgeSource.STATUS_INDEXED,
                metadata=dict(payload.metadata or {}),
            )
        )
    if chunks_to_create:
        AIKnowledgeChunk.objects.bulk_create(chunks_to_create)
    return len(chunks_to_create)


def index_source(
    *,
    source_type: str,
    source_id: str,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    document = extract_text_for_source(source_type=source_type, source_id=str(source_id))
    source = get_source(source_type=source_type, source_id=str(source_id))
    unchanged = (
        source is not None
        and source.content_hash == document.content_hash
        and source.status == AIKnowledgeSource.STATUS_INDEXED
    )
    if unchanged and not force:
        return {"indexed": False, "skipped": True, "chunks": 0, "source_id": str(source_id)}
    if dry_run:
        return {"indexed": False, "skipped": False, "chunks": 0, "source_id": str(source_id), "dry_run": True}

    with transaction.atomic():
        source = _upsert_source(document)
        source.status = AIKnowledgeSource.STATUS_PENDING
        source.last_error = ""
        source.save(update_fields=["status", "last_error", "updated_at"])
        try:
            chunk_count = _write_chunks(source, document)
            source.status = AIKnowledgeSource.STATUS_INDEXED
            source.indexed_at = timezone.now()
            source.last_error = ""
            source.save(
                update_fields=["status", "indexed_at", "last_error", "updated_at"]
            )
            return {
                "indexed": True,
                "skipped": False,
                "chunks": chunk_count,
                "source_id": str(source_id),
            }
        except Exception as exc:
            source.status = AIKnowledgeSource.STATUS_FAILED
            source.last_error = str(exc)
            source.save(update_fields=["status", "last_error", "updated_at"])
            logger.exception("Failed indexing %s:%s", source_type, source_id)
            raise


def reindex_source(*, source_type: str, source_id: str, force: bool = True, dry_run: bool = False) -> dict:
    return index_source(
        source_type=source_type,
        source_id=source_id,
        force=force,
        dry_run=dry_run,
    )


def index_all_by_source_type(
    *,
    source_type: str,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    stats = {"indexed": 0, "skipped": 0, "failed": 0, "chunks": 0, "total": 0}
    documents = list_source_documents(source_types=[source_type])
    for document in documents:
        stats["total"] += 1
        try:
            result = index_source(
                source_type=document.source_type,
                source_id=document.source_id,
                force=force,
                dry_run=dry_run,
            )
        except Exception:
            stats["failed"] += 1
            continue
        if result.get("skipped"):
            stats["skipped"] += 1
        if result.get("indexed"):
            stats["indexed"] += 1
            stats["chunks"] += int(result.get("chunks", 0))
    return stats


def mark_source_stale(*, source_type: str, source_id: str) -> bool:
    updated = AIKnowledgeSource.objects.filter(
        source_type=source_type,
        source_id=str(source_id),
    ).update(status=AIKnowledgeSource.STATUS_STALE)
    return bool(updated)


def sync_knowledge_index(
    *,
    source_types: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    source_types = source_types or SUPPORTED_SOURCE_TYPES
    stats = {
        "total_source_documents": 0,
        "indexed_documents": 0,
        "indexed_chunks": 0,
        "skipped_documents": 0,
        "failed_documents": 0,
        "deactivated_documents": 0,
    }
    active_keys = set()

    for source_type in source_types:
        documents = list_source_documents(source_types=[source_type])
        stats["total_source_documents"] += len(documents)
        for document in documents:
            active_keys.add((document.source_type, document.source_id))
            try:
                result = index_source(
                    source_type=document.source_type,
                    source_id=document.source_id,
                    force=force,
                    dry_run=dry_run,
                )
            except Exception:
                stats["failed_documents"] += 1
                continue
            if result.get("skipped"):
                stats["skipped_documents"] += 1
            if result.get("indexed"):
                stats["indexed_documents"] += 1
                stats["indexed_chunks"] += int(result.get("chunks", 0))

    for source in AIKnowledgeSource.objects.filter(source_type__in=source_types):
        if (source.source_type, source.source_id) in active_keys:
            continue
        if source.status != AIKnowledgeSource.STATUS_DISABLED:
            source.status = AIKnowledgeSource.STATUS_DISABLED
            source.save(update_fields=["status", "updated_at"])
            stats["deactivated_documents"] += 1
    return stats
