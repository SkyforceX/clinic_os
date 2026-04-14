from pathlib import Path

import pytest
from django.template import engines


BASE_DIR = Path(__file__).resolve().parents[1]


def _discover_template_files():
    template_roots = [BASE_DIR / "templates"]
    template_roots.extend((BASE_DIR / "apps").glob("*/templates"))

    files = []
    for root in template_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.html"):
            parts = set(path.parts)
            if ".claude" in parts or "backup" in parts:
                continue
            files.append(path)
    return sorted(files)


@pytest.mark.smoke
@pytest.mark.parametrize("template_path", _discover_template_files())
def test_templates_compile_without_invalid_tags_or_filters(template_path):
    raw = template_path.read_text(encoding="utf-8")
    template = engines["django"].from_string(raw)
    assert template is not None
