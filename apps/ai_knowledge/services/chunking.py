from __future__ import annotations

import re
from dataclasses import dataclass

from .clean_text import clean_text


@dataclass
class ChunkPayload:
    chunk_index: int
    content: str
    section_key: str
    title: str
    section_title: str
    token_count: int
    prev_chunk_index: int | None = None
    next_chunk_index: int | None = None
    metadata: dict | None = None


def _estimate_tokens(text: str) -> int:
    return max(1, len((text or "").split()))


def _looks_like_bullet(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^([-*•]|\d+[.)])\s+", stripped))


def _split_into_blocks(text: str) -> list[str]:
    lines = clean_text(text).split("\n")
    blocks: list[str] = []
    current: list[str] = []

    def flush():
        if current:
            blocks.append("\n".join(current).strip())
            current.clear()

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            flush()
            idx += 1
            continue

        if line.lower().startswith("q:") and idx + 1 < len(lines):
            answer_lines = [line]
            idx += 1
            while idx < len(lines):
                answer_line = lines[idx].strip()
                if not answer_line:
                    break
                answer_lines.append(answer_line)
                if answer_line.lower().startswith("a:"):
                    idx += 1
                    while idx < len(lines) and lines[idx].strip():
                        answer_lines.append(lines[idx].strip())
                        idx += 1
                    break
                idx += 1
            flush()
            blocks.append("\n".join(answer_lines).strip())
            continue

        if _looks_like_bullet(line):
            bullet_lines = [line]
            idx += 1
            while idx < len(lines):
                next_line = lines[idx].strip()
                if not next_line or not _looks_like_bullet(next_line):
                    break
                bullet_lines.append(next_line)
                idx += 1
            flush()
            blocks.append("\n".join(bullet_lines).strip())
            continue

        current.append(line)
        idx += 1

    flush()
    return [block for block in blocks if block]


def _split_large_block(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]

    sentences = re.split(r"(?<=[.!?])\s+", block)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            parts.append(current)
        if len(sentence) <= max_chars:
            current = sentence
            continue
        start = 0
        while start < len(sentence):
            end = min(start + max_chars, len(sentence))
            parts.append(sentence[start:end].strip())
            start = end
        current = ""

    if current:
        parts.append(current)
    return [part for part in parts if part]


def split_text_into_chunks(
    text: str,
    max_chars: int = 1200,
    overlap_chars: int = 160,
) -> list[str]:
    blocks = _split_into_blocks(text)
    chunks: list[str] = []
    current = ""

    for block in blocks:
        for part in _split_large_block(block, max_chars):
            candidate = f"{current}\n\n{part}".strip() if current else part
            if len(candidate) <= max_chars:
                current = candidate
                continue

            if current:
                chunks.append(current)
                overlap = current[-overlap_chars:].strip()
                current = f"{overlap}\n\n{part}".strip() if overlap else part
            else:
                chunks.append(part)

            while len(current) > max_chars:
                chunks.append(current[:max_chars].strip())
                current = current[max_chars - overlap_chars :].strip()

    if current:
        chunks.append(current)

    deduped: list[str] = []
    for chunk in chunks:
        normalized = chunk.strip()
        if normalized and (not deduped or deduped[-1] != normalized):
            deduped.append(normalized)
    return deduped


def create_chunks(
    text: str,
    *,
    title: str = "",
    section_title: str = "",
    section_key: str = "default",
    max_chars: int = 1200,
    overlap_chars: int = 160,
    metadata: dict | None = None,
) -> list[ChunkPayload]:
    chunks = split_text_into_chunks(
        text,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )
    payloads: list[ChunkPayload] = []
    for index, chunk in enumerate(chunks):
        payloads.append(
            ChunkPayload(
                chunk_index=index,
                content=chunk,
                section_key=section_key,
                title=title,
                section_title=section_title or title,
                token_count=_estimate_tokens(chunk),
                prev_chunk_index=index - 1 if index > 0 else None,
                next_chunk_index=index + 1 if index + 1 < len(chunks) else None,
                metadata=dict(metadata or {}),
            )
        )
    return payloads
