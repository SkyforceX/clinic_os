from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class PdfConversionError(RuntimeError):
    pass


class PdfConversionTimeoutError(PdfConversionError):
    pass


def _prefer_console_office_binary(path: str) -> str:
    if os.name != "nt":
        return path

    normalized = (path or "").strip()
    if not normalized:
        return path

    lower = normalized.lower()
    if not lower.endswith("soffice.exe"):
        return path

    console_path = normalized[:-4] + ".com"
    return console_path if os.path.exists(console_path) else path


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
        candidates.append(_prefer_console_office_binary(configured))
        candidates.append(configured)

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            found = _prefer_console_office_binary(found)
            candidates.append(found)

    if os.name == "nt":
        windows_candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.com",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for path in windows_candidates:
            if os.path.exists(path):
                candidates.append(path)

    return _dedupe_paths(candidates)


def _run_office_convert(office_bin: str, docx_file: Path, out_dir: Path) -> bytes:
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

        try:
            completed = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise PdfConversionTimeoutError(
                f"Hệ thống chưa hoàn tất quá trình phát hành PDF trong {timeout} giay. "
                "Vui lòng thử lại hoặc liên hệ quản trị hệ thống để kiểm tra cấu hình máy chủ."
            ) from exc

    if completed.returncode != 0:
        stdout = completed.stdout.decode("utf-8", errors="ignore").strip()
        stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
        logger.warning(
            "LibreOffice convert failed. bin=%s returncode=%s stdout=%s stderr=%s",
            office_bin,
            completed.returncode,
            stdout,
            stderr,
        )
        detail = stderr or stdout or "Khong nhan duoc thong bao loi chi tiet."
        raise PdfConversionError(
            "LibreOffice khong chuyen doi duoc file PDF. "
            f"Chi tiet ky thuat: {detail[:300]}"
        )

    if not pdf_path.exists():
        logger.warning("LibreOffice convert finished but PDF not found: %s", pdf_path)
        raise PdfConversionError(
            "LibreOffice da chay xong nhung khong tao ra file PDF. "
            "Vui long bao quan tri he thong kiem tra cau hinh convert."
        )

    pdf_bytes = pdf_path.read_bytes()
    if not pdf_bytes:
        logger.warning("LibreOffice created empty PDF: %s", pdf_path)
        raise PdfConversionError(
            "LibreOffice tao ra file PDF rong. Vui long bao quan tri he thong kiem tra template va engine convert."
        )

    return pdf_bytes


def convert_docx_to_pdf_via_office(docx_path: str, *, strict: bool = False) -> bytes | None:
    docx_file = Path(docx_path).resolve()
    if not docx_file.exists():
        message = f"DOCX file does not exist for LibreOffice convert: {docx_file}"
        logger.warning(message)
        if strict:
            raise PdfConversionError(
                "Khong tim thay file DOCX tam de chuyen doi PDF. "
                "Vui long thu lai hoac bao quan tri he thong."
            )
        return None

    out_dir = docx_file.parent
    office_bins = _candidate_office_binaries()
    if not office_bins:
        if strict:
            raise PdfConversionError(
                "Khong tim thay LibreOffice tren he thong. "
                "Can cai dat hoac cau hinh duong dan soffice truoc khi phat hanh PDF."
            )
        return None

    last_error: Exception | None = None

    for office_bin in office_bins:
        try:
            pdf_bytes = _run_office_convert(office_bin, docx_file, out_dir)
            if pdf_bytes:
                return pdf_bytes
        except PdfConversionTimeoutError:
            raise
        except (PdfConversionError, subprocess.SubprocessError, OSError, TimeoutError) as exc:
            last_error = exc
            logger.warning("LibreOffice convert exception with %s: %s", office_bin, exc)
            continue

    if strict:
        if isinstance(last_error, PdfConversionError):
            raise last_error
        raise PdfConversionError(
            "Khong the phat hanh PDF bang LibreOffice. Vui long bao quan tri he thong kiem tra engine convert."
        )

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
        prefer_html = bool(getattr(settings, "PDF_PREFER_HTML", False))

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
