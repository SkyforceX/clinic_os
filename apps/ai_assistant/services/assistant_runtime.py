from __future__ import annotations

import logging

from .profiles import get_assistant_profile_config
from .prompting import format_context_chunks
from .retrieval import retrieve_context_for_question


logger = logging.getLogger(__name__)


def build_knowledge_context(
    question: str,
    *,
    user,
    profile: str,
    source_types: list[str] | None = None,
    locale: str = "vi",
) -> str:
    profile_config = get_assistant_profile_config(profile)
    scoped_source_types = source_types or profile_config.get("allowed_source_types")
    chunks = retrieve_context_for_question(
        user=user,
        question=question,
        source_types=scoped_source_types,
        locale=locale,
    )
    return format_context_chunks(chunks)
