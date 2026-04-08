"""
pdf_converter.py
----------------
Chuyển đổi docx → PDF qua LibreOffice hoặc WeasyPrint.

Xử lý thêm sau restart:
- Dọn lock file LibreOffice (.~lock.*) còn sót từ phiên trước
- Profile dir riêng biệt mỗi lần chạy để tránh xung đột
- Timeout rõ ràng, không để process treo vô hạn
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LibreOffice binary detection
# ---------------------------------------------------------------------------

def _candidate_office_binaries() -> list[str]:
    candidates: list[str] = []

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

    unique: list[str] = []
    seen = set()
    for item in candidates:
        norm = os.path.normcase(os.path.abspath(item))
        if norm not in seen:
            seen.add(norm)
            unique.append(item)

    return unique


# ---------------------------------------------------------------------------
# Lock file cleanup (quan trọng sau khi server restart)
# ---------------------------------------------------------------------------

def _cleanup_libreoffice_locks(directory: Path) -> None:
    """
    Xóa các file lock mà LibreOffice để lại sau khi crash hoặc restart.
    Pattern: .~lock.<filename>.docx#
    """
    try:
        lock_patterns = [
            str(directory / ".~lock.*.docx#"),
            str(directory / ".~lock.*.pdf#"),
            str(directory / ".~lock.*#"),
        ]
        for pattern in lock_patterns:
            for lock_file in glob.glob(pattern):
                try:
                    os.remove(lock_file)
                    logger.info("Đã xóa lock file LibreOffice: %s", lock_file)
                except OSError:
                    pass
    except Exception as exc:
        logger.warning("Không thể dọn lock files: %s", exc)


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def _run_office_convert(office_bin: str, docx_file: Path, out_dir: Path) -> bytes | None:
    pdf_path = out_dir / f"{docx_file.stem}.pdf"
    if pdf_path.exists():
        pdf_path.unlink()

    # Dọn lock cũ trước khi chạy
    _cleanup_libreoffice_locks(out_dir)
    _cleanup_libreoffice_locks(docx_file.parent)

    with tempfile.TemporaryDirectory(prefix="lo_profile_") as profile_dir:
        profile_uri = Path(profile_dir).resolve().as_uri()
        cmd = [
            office_bin,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--norestore",
            "--nolockcheck",
            "--invisible",
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
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            logger.warning("LibreOffice timeout khi convert %s", docx_file.name)
            return None
        except OSError as exc:
            logger.warning("Không thể chạy LibreOffice (%s): %s", office_bin, exc)
            return None

    if completed.returncode != 0:
        stderr_msg = completed.stderr.decode("utf-8", errors="replace")[:500]
        logger.warning(
            "LibreOffice trả về lỗi (returncode=%s): %s",
            completed.returncode,
            stderr_msg,
        )
        return None

    if not pdf_path.exists():
        logger.warning("LibreOffice chạy OK nhưng không tạo ra file PDF: %s", pdf_path)
        return None

    pdf_bytes = pdf_path.read_bytes()
    if not pdf_bytes:
        logger.warning("File PDF được tạo nhưng rỗng: %s", pdf_path)
        return None

    return pdf_bytes


def convert_docx_to_pdf_via_office(docx_path: str) -> bytes | None:
    docx_file = Path(docx_path).resolve()
    if not docx_file.exists():
        logger.warning("Docx không tồn tại: %s", docx_path)
        return None

    out_dir = docx_file.parent
    candidates = _candidate_office_binaries()

    if not candidates:
        logger.warning("Không tìm thấy LibreOffice trên hệ thống.")
        return None

    for office_bin in candidates:
        try:
            pdf_bytes = _run_office_convert(office_bin, docx_file, out_dir)
            if pdf_bytes:
                return pdf_bytes
        except Exception as exc:
            logger.warning("LibreOffice (%s) lỗi: %s", office_bin, exc)
            continue

    return None


def convert_html_to_pdf_via_weasyprint(
    html_string: str,
    base_url: str | None = None,
) -> bytes | None:
    try:
        import weasyprint
    except ImportError:
        # Chưa cài — bình thường, LibreOffice là primary
        logger.debug("WeasyPrint chưa cài đặt, bỏ qua fallback.")
        return None
    except OSError:
        # DLL conflict phổ biến trên Windows (Tesseract, GIMP, v.v.)
        # Không phải lỗi nghiêm trọng — LibreOffice đã xử lý PDF rồi
        logger.debug(
            "WeasyPrint không load được DLL trên Windows "
            "(conflict với Tesseract/GTK). Bỏ qua — LibreOffice là công cụ chính."
        )
        return None
    except Exception:
        logger.debug("WeasyPrint không khởi động được, bỏ qua fallback.")
        return None

    try:
        return weasyprint.HTML(string=html_string, base_url=base_url).write_pdf()
    except Exception as exc:
        logger.debug("WeasyPrint lỗi khi render PDF: %s", exc)
        return None


def build_pdf_bytes(
    *,
    docx_path: str,
    fallback_html: str | None = None,
    base_url: str | None = None,
) -> bytes | None:
    """
    Thử convert docx → PDF qua LibreOffice trước.
    Nếu fail, thử lại bằng WeasyPrint từ HTML fallback.
    Trả None nếu cả hai đều thất bại.
    """
    pdf_bytes = convert_docx_to_pdf_via_office(docx_path)
    if pdf_bytes:
        logger.info("PDF tạo thành công qua LibreOffice.")
        return pdf_bytes

    if fallback_html:
        logger.info("LibreOffice thất bại, thử fallback WeasyPrint...")
        pdf_bytes = convert_html_to_pdf_via_weasyprint(fallback_html, base_url=base_url)
        if pdf_bytes:
            logger.info("PDF tạo thành công qua WeasyPrint (fallback).")
            return pdf_bytes

    logger.error(
        "Không thể tạo PDF. "
        "Kiểm tra: (1) LibreOffice đã cài tại %s; "
        "(2) weasyprint (pip install weasyprint); "
        "(3) quyền ghi thư mục MEDIA_ROOT; "
        "(4) lock files LibreOffice còn sót sau restart.",
        _candidate_office_binaries() or "không tìm thấy",
    )
    return None