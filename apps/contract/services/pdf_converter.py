from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def _dedupe_paths(paths: list[str]) -> list[str]:
    unique: list[str] = []
    seen = set()

    for item in paths:
        if not item:
            continue
        norm = os.path.normcase(os.path.abspath(item))
        if norm in seen:
            continue
        seen.add(norm)
        unique.append(item)

    return unique


def _candidate_office_binaries() -> list[str]:
    candidates: list[str] = []

    configured = getattr(settings, "LIBREOFFICE_PATH", "") or os.getenv("LIBREOFFICE_PATH", "")
    if configured:
        candidates.append(configured)

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    if os.name == "nt":
        windows_candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for path in windows_candidates:
            if os.path.exists(path):
                candidates.append(path)

    return _dedupe_paths(candidates)


def _run_office_convert(office_bin: str, docx_file: Path, out_dir: Path) -> bytes | None:
    pdf_path = out_dir / f"{docx_file.stem}.pdf"
    if pdf_path.exists():
        pdf_path.unlink()

    timeout = int(getattr(settings, "PDF_CONVERT_TIMEOUT", 180) or 180)

    with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile_dir:
        profile_uri = Path(profile_dir).resolve().as_uri()
        cmd = [
            office_bin,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(out_dir),
            str(docx_file),
        ]

        completed = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

    if completed.returncode != 0:
        logger.warning(
            "LibreOffice convert failed. bin=%s returncode=%s stdout=%s stderr=%s",
            office_bin,
            completed.returncode,
            completed.stdout.decode("utf-8", errors="ignore"),
            completed.stderr.decode("utf-8", errors="ignore"),
        )
        return None

    if not pdf_path.exists():
        logger.warning("LibreOffice convert finished but PDF not found: %s", pdf_path)
        return None

    pdf_bytes = pdf_path.read_bytes()
    if not pdf_bytes:
        logger.warning("LibreOffice created empty PDF: %s", pdf_path)
        return None

    return pdf_bytes


def convert_docx_to_pdf_via_office(docx_path: str) -> bytes | None:
    docx_file = Path(docx_path).resolve()
    if not docx_file.exists():
        logger.warning("DOCX file does not exist for LibreOffice convert: %s", docx_file)
        return None

    out_dir = docx_file.parent

    for office_bin in _candidate_office_binaries():
        try:
            pdf_bytes = _run_office_convert(office_bin, docx_file, out_dir)
            if pdf_bytes:
                return pdf_bytes
        except (subprocess.SubprocessError, OSError, TimeoutError) as exc:
            logger.warning("LibreOffice convert exception with %s: %s", office_bin, exc)
            continue

    return None


def convert_html_to_pdf_via_weasyprint(html_string: str, base_url: str | None = None) -> bytes | None:
    try:
        from weasyprint import HTML
    except ImportError:
        logger.warning("WeasyPrint is not installed.")
        return None
    except Exception as exc:
        logger.warning("WeasyPrint import failed (missing system libraries like cairo/pango): %s", exc)
        return None

    try:
        return HTML(string=html_string, base_url=base_url).write_pdf()
    except Exception as exc:
        logger.warning(
            "WeasyPrint render failed. Check if system libraries are installed "
            "(Windows: weasyprint-docs.readthedocs.io). Error: %s",
            exc
        )
        return None


def build_pdf_bytes(
    *,
    docx_path: str,
    fallback_html: str | None = None,
    base_url: str | None = None,
    prefer_html: bool | None = None,
) -> bytes | None:
    engine = (getattr(settings, "PDF_ENGINE", "auto") or "auto").strip().lower()

    if prefer_html is None:
        prefer_html = bool(getattr(settings, "PDF_PREFER_HTML", True))

    def _html_first() -> bytes | None:
        if fallback_html:
            pdf_bytes = convert_html_to_pdf_via_weasyprint(fallback_html, base_url=base_url)
            if pdf_bytes:
                return pdf_bytes
        return convert_docx_to_pdf_via_office(docx_path)

    def _office_first() -> bytes | None:
        pdf_bytes = convert_docx_to_pdf_via_office(docx_path)
        if pdf_bytes:
            return pdf_bytes
        if fallback_html:
            return convert_html_to_pdf_via_weasyprint(fallback_html, base_url=base_url)
        return None

    if engine == "weasy":
        if fallback_html:
            return convert_html_to_pdf_via_weasyprint(fallback_html, base_url=base_url)
        return None

    if engine == "libreoffice":
        return convert_docx_to_pdf_via_office(docx_path)

    # auto
    return _html_first() if prefer_html else _office_first()