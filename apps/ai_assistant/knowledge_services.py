from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from apps.catalogs.models import CheckupCategory, CheckupPackageTemplate
from apps.procedures.models import Procedure

from .models import KnowledgeChunk, KnowledgeDocument
from .selectors import (
    list_active_checkup_categories_for_knowledge,
    list_active_checkup_packages_for_knowledge,
    list_active_knowledge_chunks,
    list_allowed_knowledge_source_types_for_user,
    list_published_procedures_for_knowledge,
)

logger = logging.getLogger(__name__)


def _is_loopback_url(url: str) -> bool:
    hostname = urlparse((url or "").strip()).hostname
    return hostname in {"127.0.0.1", "localhost", "::1"}


@dataclass
class SourceDocument:
    source_type: str
    source_id: int
    title: str
    content: str
    metadata: dict
    source_updated_at: datetime | None = None


def get_embedding_base_url() -> str:
    embed_url = getattr(settings, "AI_EMBED_BASE_URL", "").strip()
    ollama_url = getattr(settings, "OLLAMA_BASE_URL", "").strip()
    ai_url = getattr(settings, "AI_BASE_URL", "").strip()

    candidates = [url for url in (embed_url, ollama_url, ai_url) if url]
    if not candidates:
        return "http://127.0.0.1:11434"

    non_loopback_candidates = [url for url in candidates if not _is_loopback_url(url)]
    selected_url = non_loopback_candidates[0] if non_loopback_candidates else candidates[0]
    return selected_url.rstrip("/")


def get_embedding_model() -> str:
    return getattr(settings, "AI_EMBED_MODEL", "nomic-embed-text").strip()


def get_knowledge_top_k() -> int:
    return int(getattr(settings, "AI_KNOWLEDGE_TOP_K", 5))


def is_knowledge_enabled() -> bool:
    return bool(getattr(settings, "AI_KNOWLEDGE_ENABLED", True))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean_text(value: str) -> str:
    lines = [strip_tags((value or "").replace("\r", "")).strip() for value in (value or "").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _join_non_empty(parts: Iterable[str]) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _build_procedure_document(procedure: Procedure) -> SourceDocument:
    step_blocks = []
    for step in procedure.steps.all():
        step_parts = [
            f"Bước: {step.title}",
            f"Phụ trách: {step.responsible}" if step.responsible else "",
            f"Thời gian: {step.duration}" if step.duration else "",
            _clean_text(step.description),
        ]
        step_blocks.append(_join_non_empty(step_parts))

    content = _join_non_empty(
        [
            "Loại tài liệu: Quy trình nội bộ",
            f"Tiêu đề: {procedure.title}",
            f"Mã quy trình: {procedure.code}" if procedure.code else "",
            f"Loại: {procedure.get_category_display()}",
            f"Phiên bản: {procedure.version}" if procedure.version else "",
            f"Hiệu lực: {procedure.effective_date:%d/%m/%Y}" if procedure.effective_date else "",
            _clean_text(procedure.description),
            "\n\n".join(step_blocks),
        ]
    )
    return SourceDocument(
        source_type=KnowledgeDocument.SOURCE_PROCEDURE,
        source_id=procedure.pk,
        title=procedure.title,
        content=content,
        metadata={
            "code": procedure.code,
            "category": procedure.category,
            "status": procedure.status,
            "version": procedure.version,
        },
        source_updated_at=procedure.updated_at,
    )


def _build_category_document(category: CheckupCategory) -> SourceDocument:
    content = _join_non_empty(
        [
            "Loại tài liệu: Danh mục khám",
            f"Nhóm khám: {category.group_checkup.name}",
            f"Tiểu nhóm: {category.subgroup_name}" if category.subgroup_name else "",
            f"Tên hạng mục: {category.item_name}",
            f"Mã: {category.item_code}" if category.item_code else "",
            _clean_text(category.description or ""),
            f"Ghi chú: {category.note}" if category.note else "",
            f"Áp dụng nam: {'Có' if category.for_male else 'Không'}",
            f"Áp dụng nữ độc thân: {'Có' if category.for_female_single else 'Không'}",
            f"Áp dụng nữ gia đình: {'Có' if category.for_female_family else 'Không'}",
        ]
    )
    return SourceDocument(
        source_type=KnowledgeDocument.SOURCE_CATEGORY,
        source_id=category.pk,
        title=category.item_name,
        content=content,
        metadata={
            "group_name": category.group_checkup.name,
            "item_code": category.item_code,
            "price_type": category.price_type,
        },
        source_updated_at=category.updated_at,
    )


def _build_package_document(package: CheckupPackageTemplate) -> SourceDocument:
    item_blocks = []
    for item in package.items.all():
        category = item.category
        item_blocks.append(
            _join_non_empty(
                [
                    f"Hạng mục: {category.item_name}",
                    f"Nhóm: {category.group_checkup.name}",
                    _clean_text(category.description or ""),
                    f"Ghi chú: {category.note}" if category.note else "",
                ]
            )
        )

    content = _join_non_empty(
        [
            "Loại tài liệu: Gói khám mẫu",
            f"Tên gói: {package.name}",
            _clean_text(package.description),
            f"Số hạng mục: {package.items.count()}",
            "\n\n".join(item_blocks),
        ]
    )
    return SourceDocument(
        source_type=KnowledgeDocument.SOURCE_PACKAGE,
        source_id=package.pk,
        title=package.name,
        content=content,
        metadata={
            "item_count": package.items.count(),
            "created_by_id": package.created_by_id,
        },
        source_updated_at=package.updated_at,
    )


def list_source_documents(source_types: list[str] | None = None) -> list[SourceDocument]:
    source_types = source_types or [
        KnowledgeDocument.SOURCE_PROCEDURE,
        KnowledgeDocument.SOURCE_CATEGORY,
        KnowledgeDocument.SOURCE_PACKAGE,
    ]
    documents: list[SourceDocument] = []

    if KnowledgeDocument.SOURCE_PROCEDURE in source_types:
        documents.extend(
            _build_procedure_document(procedure)
            for procedure in list_published_procedures_for_knowledge()
        )

    if KnowledgeDocument.SOURCE_CATEGORY in source_types:
        documents.extend(
            _build_category_document(category)
            for category in list_active_checkup_categories_for_knowledge()
        )

    if KnowledgeDocument.SOURCE_PACKAGE in source_types:
        documents.extend(
            _build_package_document(package)
            for package in list_active_checkup_packages_for_knowledge()
        )

    return documents


def split_text_into_chunks(text: str, max_chars: int = 1200, overlap_chars: int = 160) -> list[str]:
    cleaned_text = _clean_text(text)
    if not cleaned_text:
        return []

    paragraphs = [part.strip() for part in cleaned_text.split("\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            overlap = current[-overlap_chars:].strip()
            current = f"{overlap}\n{paragraph}".strip() if overlap else paragraph
        else:
            start = 0
            while start < len(paragraph):
                end = min(start + max_chars, len(paragraph))
                chunks.append(paragraph[start:end].strip())
                if end >= len(paragraph):
                    current = ""
                    break
                start = max(end - overlap_chars, start + 1)

        while len(current) > max_chars:
            chunks.append(current[:max_chars].strip())
            current = current[max_chars - overlap_chars :].strip()

    if current:
        chunks.append(current)

    deduped_chunks = []
    for chunk in chunks:
        normalized = chunk.strip()
        if normalized and (not deduped_chunks or deduped_chunks[-1] != normalized):
            deduped_chunks.append(normalized)
    return deduped_chunks


def _post_embed_request(url: str, payload: dict, timeout: int = 60) -> requests.Response:
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = get_embedding_model()
    if not model:
        raise RuntimeError("Chưa cấu hình AI_EMBED_MODEL để tạo vector.")

    base_url = get_embedding_base_url()
    try:
        response = _post_embed_request(
            f"{base_url}/api/embed",
            {"model": model, "input": texts},
        )
        data = response.json()
        embeddings = data.get("embeddings") or []
        if len(embeddings) != len(texts):
            raise RuntimeError("Số lượng embedding trả về không khớp số chunk cần index.")
        return embeddings
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code != 404:
            raise

    embeddings = []
    for text in texts:
        response = _post_embed_request(
            f"{base_url}/api/embeddings",
            {"model": model, "prompt": text},
        )
        data = response.json()
        embedding = data.get("embedding")
        if not embedding:
            raise RuntimeError("API embedding không trả về vector hợp lệ.")
        embeddings.append(embedding)
    return embeddings


def sync_knowledge_index(source_types: list[str] | None = None) -> dict:
    if not is_knowledge_enabled():
        return {"indexed_documents": 0, "indexed_chunks": 0, "deactivated_documents": 0}

    source_documents = list_source_documents(source_types=source_types)
    document_keys = {(doc.source_type, doc.source_id) for doc in source_documents}

    existing_documents = {
        (doc.source_type, doc.source_id): doc
        for doc in KnowledgeDocument.records.filter(
            source_type__in=(source_types or [choice for choice, _ in KnowledgeDocument.SOURCE_CHOICES])
        )
    }

    indexed_documents = 0
    indexed_chunks = 0

    for source_document in source_documents:
        content_hash = _sha256(source_document.content)
        document = existing_documents.get((source_document.source_type, source_document.source_id))
        needs_reindex = (
            document is None
            or document.content_hash != content_hash
            or not document.is_active
        )

        with transaction.atomic():
            if document is None:
                document = KnowledgeDocument.records.create(
                    source_type=source_document.source_type,
                    source_id=source_document.source_id,
                    title=source_document.title,
                    content=source_document.content,
                    metadata=source_document.metadata,
                    content_hash=content_hash,
                    is_active=True,
                    source_updated_at=source_document.source_updated_at,
                )
            else:
                update_fields = [
                    "title",
                    "content",
                    "metadata",
                    "content_hash",
                    "is_active",
                    "source_updated_at",
                    "last_indexed_at",
                ]
                document.title = source_document.title
                document.content = source_document.content
                document.metadata = source_document.metadata
                document.content_hash = content_hash
                document.is_active = True
                document.source_updated_at = source_document.source_updated_at
                document.last_indexed_at = timezone.now()
                document.save(update_fields=update_fields)

            if needs_reindex:
                chunk_texts = split_text_into_chunks(source_document.content)
                embeddings = embed_texts(chunk_texts) if chunk_texts else []
                document.chunks.all().delete()
                chunks_to_create = []
                for idx, chunk_text in enumerate(chunk_texts):
                    chunks_to_create.append(
                        KnowledgeChunk(
                            document=document,
                            chunk_index=idx,
                            content=chunk_text,
                            metadata={"title": source_document.title},
                            content_hash=_sha256(chunk_text),
                            embedding=embeddings[idx],
                            char_count=len(chunk_text),
                        )
                    )
                if chunks_to_create:
                    KnowledgeChunk.records.bulk_create(chunks_to_create)
                    indexed_chunks += len(chunks_to_create)
                indexed_documents += 1

    missing_documents = []
    for key, document in existing_documents.items():
        if key not in document_keys and document.is_active:
            document.is_active = False
            document.last_indexed_at = timezone.now()
            missing_documents.append(document)

    if missing_documents:
        KnowledgeDocument.records.bulk_update(missing_documents, ["is_active", "last_indexed_at"])

    return {
        "indexed_documents": indexed_documents,
        "indexed_chunks": indexed_chunks,
        "deactivated_documents": len(missing_documents),
        "total_source_documents": len(source_documents),
    }


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return -1.0

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return -1.0

    dot_product = sum(l_value * r_value for l_value, r_value in zip(left, right))
    return dot_product / (left_norm * right_norm)


def retrieve_relevant_chunks(query: str, user, top_k: int | None = None) -> list[tuple[KnowledgeChunk, float]]:
    if not is_knowledge_enabled():
        return []

    source_types = list_allowed_knowledge_source_types_for_user(user)
    if not source_types:
        return []

    query = (query or "").strip()
    if not query:
        return []

    try:
        query_embedding = embed_texts([query])[0]
    except Exception as exc:
        logger.warning("Không tạo được embedding cho query: %s", exc)
        return []

    scored_chunks = []
    for chunk in list_active_knowledge_chunks(source_types=source_types):
        score = _cosine_similarity(query_embedding, chunk.embedding)
        if score > 0:
            scored_chunks.append((chunk, score))

    scored_chunks.sort(key=lambda item: item[1], reverse=True)
    return scored_chunks[: (top_k or get_knowledge_top_k())]


def build_knowledge_context(query: str, user) -> str:
    relevant_chunks = retrieve_relevant_chunks(query, user=user)
    if not relevant_chunks:
        return ""

    context_parts = [
        "Dưới đây là tri thức nội bộ liên quan. Chỉ sử dụng nếu thật sự phù hợp với câu hỏi.",
        "Nếu dữ kiện chưa đủ chắc chắn, hãy nói rõ cần kiểm tra thêm thay vì tự suy đoán.",
    ]
    for index, (chunk, score) in enumerate(relevant_chunks, start=1):
        context_parts.append(
            _join_non_empty(
                [
                    f"[Nguồn {index}] {chunk.document.title}",
                    f"Loại: {chunk.document.get_source_type_display()}",
                    f"Độ liên quan: {score:.3f}",
                    chunk.content,
                ]
            )
        )

    return "\n\n".join(context_parts)
