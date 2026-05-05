from django.db import migrations


def _normalize_embedding(value):
    if value in (None, ""):
        return None
    if isinstance(value, list):
        return [float(item) for item in value]
    if isinstance(value, tuple):
        return [float(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("[") and stripped.endswith("]"):
            body = stripped[1:-1].strip()
            if not body:
                return []
            return [float(part.strip()) for part in body.split(",")]
    return None


def migrate_legacy_ai_assistant_knowledge(apps, schema_editor):
    LegacyDocument = apps.get_model("ai_assistant", "KnowledgeDocument")
    LegacyChunk = apps.get_model("ai_assistant", "KnowledgeChunk")
    AIKnowledgeSource = apps.get_model("ai_knowledge", "AIKnowledgeSource")
    AIKnowledgeChunk = apps.get_model("ai_knowledge", "AIKnowledgeChunk")

    legacy_document_manager = LegacyDocument._base_manager
    legacy_chunk_manager = LegacyChunk._base_manager
    source_manager = AIKnowledgeSource._base_manager
    chunk_manager = AIKnowledgeChunk._base_manager

    for legacy_document in legacy_document_manager.all().order_by("pk"):
        status = "indexed" if legacy_document.is_active else "disabled"
        source, _ = source_manager.update_or_create(
            source_type=legacy_document.source_type,
            source_id=str(legacy_document.source_id),
            defaults={
                "title": legacy_document.title,
                "source_url": "",
                "locale": "vi",
                "status": status,
                "content_hash": legacy_document.content_hash,
                "indexed_at": legacy_document.last_indexed_at,
                "last_error": "",
                "access_level": "internal",
                "metadata": legacy_document.metadata or {},
                "created_at": legacy_document.created_at,
                "updated_at": legacy_document.last_indexed_at or legacy_document.created_at,
            },
        )

        for legacy_chunk in legacy_chunk_manager.filter(document_id=legacy_document.pk).order_by("chunk_index"):
            embedding_value = _normalize_embedding(getattr(legacy_chunk, "embedding_vector", None))
            if embedding_value is None:
                embedding_value = _normalize_embedding(legacy_chunk.embedding)

            chunk_manager.update_or_create(
                source_record=source,
                chunk_index=legacy_chunk.chunk_index,
                defaults={
                    "source_type": source.source_type,
                    "source_id": source.source_id,
                    "section_key": (legacy_chunk.metadata or {}).get("section_key", "default"),
                    "title": source.title,
                    "section_title": source.title,
                    "content": legacy_chunk.content,
                    "embedding": embedding_value,
                    "embedding_model": "legacy-ai-assistant",
                    "embedding_dim": len(embedding_value or []),
                    "token_count": max(1, len((legacy_chunk.content or "").split())),
                    "prev_chunk_index": legacy_chunk.chunk_index - 1 if legacy_chunk.chunk_index > 0 else None,
                    "next_chunk_index": legacy_chunk.chunk_index + 1,
                    "access_level": source.access_level,
                    "locale": source.locale,
                    "status": "indexed" if source.status == "indexed" else "disabled",
                    "metadata": legacy_chunk.metadata or {},
                    "created_at": legacy_chunk.created_at,
                    "updated_at": legacy_document.last_indexed_at or legacy_chunk.created_at,
                },
            )

    for source in source_manager.all():
        source_chunks = chunk_manager.filter(source_record=source).order_by("chunk_index")
        last_index = source_chunks.count() - 1
        for idx, chunk in enumerate(source_chunks):
            expected_next = idx + 1 if idx < last_index else None
            if chunk.prev_chunk_index != (idx - 1 if idx > 0 else None) or chunk.next_chunk_index != expected_next:
                chunk.prev_chunk_index = idx - 1 if idx > 0 else None
                chunk.next_chunk_index = expected_next
                chunk.save(update_fields=["prev_chunk_index", "next_chunk_index"])


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0004_pgvector_embedding_ann"),
        ("ai_knowledge", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            migrate_legacy_ai_assistant_knowledge,
            migrations.RunPython.noop,
        ),
    ]
