from __future__ import annotations

import logging

from celery import shared_task

from apps.ai_knowledge.services.extractors import SUPPORTED_SOURCE_TYPES
from apps.ai_knowledge.services.indexing import sync_knowledge_index

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, name="ai_knowledge.tasks.sync_ai_knowledge")
def sync_ai_knowledge_task(self, source_types: list[str] | None = None, force: bool = False):
    try:
        stats = sync_knowledge_index(
            source_types=source_types or list(SUPPORTED_SOURCE_TYPES),
            force=force,
        )
        logger.info(
            "AI knowledge sync completed — "
            "total=%s indexed=%s chunks=%s skipped=%s failed=%s deactivated=%s",
            stats["total_source_documents"],
            stats["indexed_documents"],
            stats["indexed_chunks"],
            stats["skipped_documents"],
            stats["failed_documents"],
            stats["deactivated_documents"],
        )
        return stats
    except Exception as exc:
        logger.exception("AI knowledge sync failed: %s", exc)
        raise self.retry(exc=exc, countdown=600)
