from __future__ import annotations

import re

from django.utils.html import strip_tags


SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def strip_html(text: str) -> str:
    without_scripts = SCRIPT_STYLE_RE.sub(" ", text or "")
    return strip_tags(without_scripts)


def normalize_whitespace(text: str) -> str:
    normalized_lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in (text or "").replace("\r", "").split("\n")
    ]
    collapsed = "\n".join(line for line in normalized_lines if line)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def clean_text(text: str) -> str:
    return normalize_whitespace(strip_html(text or ""))
