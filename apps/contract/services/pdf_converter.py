import os
import shutil
import subprocess
import tempfile
from pathlib import Path


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
        if norm in seen:
            continue
        seen.add(norm)
        unique.append(item)

    return unique


def _run_office_convert(office_bin: str, docx_file: Path, out_dir: Path) -> bytes | None:
    pdf_path = out_dir / f"{docx_file.stem}.pdf"
    if pdf_path.exists():
        pdf_path.unlink()

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
            condition=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )

    if completed.returncode != 0:
        return None

    if not pdf_path.exists():
        return None

    pdf_bytes = pdf_path.read_bytes()
    if not pdf_bytes:
        return None

    return pdf_bytes


def convert_docx_to_pdf_via_office(docx_path: str) -> bytes | None:
    docx_file = Path(docx_path).resolve()
    if not docx_file.exists():
        return None

    out_dir = docx_file.parent

    for office_bin in _candidate_office_binaries():
        try:
            pdf_bytes = _run_office_convert(office_bin, docx_file, out_dir)
            if pdf_bytes:
                return pdf_bytes
        except (subprocess.SubprocessError, OSError, TimeoutError):
            continue

    return None


def convert_html_to_pdf_via_weasyprint(html_string: str, base_url: str | None = None) -> bytes | None:
    try:
        import weasyprint
    except ImportError:
        return None

    return weasyprint.HTML(string=html_string, base_url=base_url).write_pdf()


def build_pdf_bytes(*, docx_path: str, fallback_html: str | None = None, base_url: str | None = None) -> bytes | None:
    pdf_bytes = convert_docx_to_pdf_via_office(docx_path)
    if pdf_bytes:
        return pdf_bytes

    if fallback_html:
        return convert_html_to_pdf_via_weasyprint(fallback_html, base_url=base_url)

    return None