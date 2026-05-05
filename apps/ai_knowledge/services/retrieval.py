from __future__ import annotations

import json
import logging
import math
import re
import unicodedata

from django.db import connection

from apps.ai_knowledge.models import AIKnowledgeChunk, AIKnowledgeSource
from apps.ai_knowledge.selectors.chunks import get_neighbor_chunks, list_indexed_chunks

from .embedding import embed_text
from .permissions import get_allowed_access_levels, get_allowed_source_types


logger = logging.getLogger(__name__)

SCOPE_KEYS = [
    "company_id",
    "organization_id",
    "customer_id",
    "contract_id",
    "quotation_id",
    "patient_id",
    "visit_id",
    "medical_record_id",
    "department",
    "owner_id",
]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(float(item), ".15g") for item in values) + "]"


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents)


def _tokenize_text(value: str) -> set[str]:
    normalized = _normalize_text(value)
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) >= 2
    }


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return -1.0
    left_norm = math.sqrt(sum(item * item for item in left))
    right_norm = math.sqrt(sum(item * item for item in right))
    if not left_norm or not right_norm:
        return -1.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _keyword_overlap_score(query: str, chunk: AIKnowledgeChunk) -> float:
    query_tokens = _tokenize_text(query)
    if not query_tokens:
        return 0.0
    haystack_tokens = _tokenize_text(
        " ".join(
            [
                chunk.title or "",
                chunk.section_title or "",
                chunk.content or "",
                json.dumps(chunk.metadata or {}, ensure_ascii=False),
            ]
        )
    )
    if not haystack_tokens:
        return 0.0
    overlap = query_tokens & haystack_tokens
    if not overlap:
        return 0.0
    return len(overlap) / len(query_tokens)


def _matches_metadata(chunk: AIKnowledgeChunk, metadata_filter: dict | None) -> bool:
    if not metadata_filter:
        return True
    chunk_metadata = chunk.metadata or {}
    return all(str(chunk_metadata.get(key)) == str(value) for key, value in metadata_filter.items())


def _matches_scope(chunk: AIKnowledgeChunk, scope_filters: dict) -> bool:
    chunk_metadata = chunk.metadata or {}
    for key, value in scope_filters.items():
        if value is None:
            continue
        if key == "source_id":
            if str(chunk.source_id) != str(value):
                return False
            continue
        if str(chunk_metadata.get(key)) != str(value):
            return False
    return True


def _serialize_chunk(chunk: AIKnowledgeChunk, similarity: float, distance: float) -> dict:
    return {
        "id": chunk.id,
        "source_id": chunk.source_id,
        "source_type": chunk.source_type,
        "section_key": chunk.section_key,
        "chunk_index": chunk.chunk_index,
        "title": chunk.title,
        "section_title": chunk.section_title,
        "content": chunk.content,
        "metadata": chunk.metadata or {},
        "distance": distance,
        "similarity": similarity,
    }


def _safe_source_types(source_types: list[str] | None, allowed_source_types: list[str]) -> list[str]:
    if source_types:
        return [source_type for source_type in source_types if source_type in allowed_source_types]
    return allowed_source_types


def search_rag_chunks(
    conn,
    query_embedding: list[float],
    allowed_access_levels: list[str],
    source_types: list[str] | None = None,
    locale: str = "vi",
    top_k: int = 8,
    max_distance: float | None = None,
    metadata_filter: dict | None = None,
    company_id: str | None = None,
    organization_id: str | None = None,
    customer_id: str | None = None,
    contract_id: str | None = None,
    quotation_id: str | None = None,
    patient_id: str | None = None,
    visit_id: str | None = None,
    medical_record_id: str | None = None,
    department: str | None = None,
):
    if not query_embedding:
        return []

    vector_literal = _vector_literal(query_embedding)
    table = AIKnowledgeChunk._meta.db_table
    where_clauses = [
        "embedding IS NOT NULL",
        "status = %s",
        "locale = %s",
    ]
    params: list[object] = [AIKnowledgeSource.STATUS_INDEXED, locale]

    if allowed_access_levels:
        placeholders = ", ".join(["%s"] * len(allowed_access_levels))
        where_clauses.append(f"access_level IN ({placeholders})")
        params.extend(allowed_access_levels)

    if source_types:
        placeholders = ", ".join(["%s"] * len(source_types))
        where_clauses.append(f"source_type IN ({placeholders})")
        params.extend(source_types)

    if max_distance is not None:
        where_clauses.append("embedding <=> %s::vector < %s")
        params.extend([vector_literal, max_distance])

    if metadata_filter:
        where_clauses.append("metadata @> %s::jsonb")
        params.append(json.dumps(metadata_filter))

    scope_values = {
        "company_id": company_id,
        "organization_id": organization_id,
        "customer_id": customer_id,
        "contract_id": contract_id,
        "quotation_id": quotation_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "medical_record_id": medical_record_id,
        "department": department,
    }
    for key, value in scope_values.items():
        if value is None:
            continue
        where_clauses.append(f"metadata->>'{key}' = %s")
        params.append(str(value))

    sql = f"""
        SELECT
            id,
            source_id,
            source_type,
            section_key,
            chunk_index,
            title,
            section_title,
            content,
            metadata,
            embedding <=> %s::vector AS distance,
            1 - (embedding <=> %s::vector) AS similarity
        FROM {table}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s
    """
    final_params = [vector_literal, vector_literal, *params, vector_literal, top_k]

    with conn.cursor() as cursor:
        cursor.execute(sql, final_params)
        rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "source_id": row[1],
                "source_type": row[2],
                "section_key": row[3],
                "chunk_index": row[4],
                "title": row[5],
                "section_title": row[6],
                "content": row[7],
                "metadata": row[8] or {},
                "distance": float(row[9]),
                "similarity": float(row[10]),
            }
        )
    return results


def _search_rag_chunks_python(
    *,
    question: str,
    query_embedding: list[float],
    allowed_access_levels: list[str],
    source_types: list[str],
    locale: str,
    top_k: int,
    max_distance: float | None,
    metadata_filter: dict | None,
    scope_filters: dict,
) -> list[dict]:
    scored_chunks = []
    for chunk in list_indexed_chunks(
        source_types=source_types,
        locale=locale,
        access_levels=allowed_access_levels,
    ):
        if not _matches_metadata(chunk, metadata_filter):
            continue
        if not _matches_scope(chunk, scope_filters):
            continue
        similarity = _cosine_similarity(query_embedding, chunk.embedding)
        if similarity <= 0:
            continue
        distance = 1 - similarity
        if max_distance is not None and distance >= max_distance:
            continue
        keyword_score = _keyword_overlap_score(question, chunk)
        final_similarity = similarity * 0.7 + keyword_score * 0.3
        scored_chunks.append((chunk, final_similarity, distance))

    scored_chunks.sort(key=lambda item: item[1], reverse=True)
    return [
        _serialize_chunk(chunk, similarity=score, distance=distance)
        for chunk, score, distance in scored_chunks[:top_k]
    ]


def expand_neighbor_chunks(
    chunks: list[dict],
    *,
    allowed_access_levels: list[str],
    locale: str = "vi",
    radius: int = 1,
) -> list[dict]:
    if not chunks:
        return []
    deduped: dict[int, dict] = {chunk["id"]: dict(chunk) for chunk in chunks}
    for chunk in chunks:
        for neighbor in get_neighbor_chunks(
            source_id=chunk["source_id"],
            source_type=chunk["source_type"],
            section_key=chunk["section_key"],
            chunk_index=chunk["chunk_index"],
            radius=radius,
            locale=locale,
            access_levels=allowed_access_levels,
        ):
            if neighbor.id in deduped:
                continue
            deduped[neighbor.id] = _serialize_chunk(
                neighbor,
                similarity=0.0,
                distance=1.0,
            )
    return sorted(
        deduped.values(),
        key=lambda item: (
            str(item["source_id"]),
            item["section_key"] or "",
            int(item["chunk_index"]),
        ),
    )


def retrieve_context_for_question(
    *,
    user,
    question: str,
    query_embedding: list[float] | None = None,
    source_types: list[str] | None = None,
    locale: str = "vi",
    top_k: int = 8,
    max_distance: float | None = None,
    metadata_filter: dict | None = None,
    company_id: str | None = None,
    organization_id: str | None = None,
    customer_id: str | None = None,
    contract_id: str | None = None,
    quotation_id: str | None = None,
    patient_id: str | None = None,
    visit_id: str | None = None,
    medical_record_id: str | None = None,
    department: str | None = None,
) -> list[dict]:
    question = (question or "").strip()
    if not question:
        return []

    allowed_access_levels = get_allowed_access_levels(user)
    allowed_source_types = _safe_source_types(
        source_types,
        get_allowed_source_types(user),
    )
    if not allowed_source_types:
        return []

    scope_filters = {
        "company_id": company_id,
        "organization_id": organization_id,
        "customer_id": customer_id,
        "contract_id": contract_id,
        "quotation_id": quotation_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "medical_record_id": medical_record_id,
        "department": department,
    }

    if query_embedding is None:
        query_embedding = embed_text(question)

    results: list[dict] = []
    if connection.vendor == "postgresql":
        try:
            results = search_rag_chunks(
                connection,
                query_embedding,
                allowed_access_levels,
                source_types=allowed_source_types,
                locale=locale,
                top_k=top_k,
                max_distance=max_distance,
                metadata_filter=metadata_filter,
                company_id=company_id,
                organization_id=organization_id,
                customer_id=customer_id,
                contract_id=contract_id,
                quotation_id=quotation_id,
                patient_id=patient_id,
                visit_id=visit_id,
                medical_record_id=medical_record_id,
                department=department,
            )
        except Exception as exc:
            logger.warning("pgvector retrieval failed, fallback to python: %s", exc)

    if not results:
        results = _search_rag_chunks_python(
            question=question,
            query_embedding=query_embedding,
            allowed_access_levels=allowed_access_levels,
            source_types=allowed_source_types,
            locale=locale,
            top_k=top_k,
            max_distance=max_distance,
            metadata_filter=metadata_filter,
            scope_filters=scope_filters,
        )

    expanded = expand_neighbor_chunks(
        results,
        allowed_access_levels=allowed_access_levels,
        locale=locale,
        radius=1,
    )
    return expanded
