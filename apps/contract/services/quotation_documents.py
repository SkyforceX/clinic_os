"""
quotation_documents.py
----------------------
Phát hành (issue) tài liệu báo giá dưới dạng docx + pdf.

Thay đổi so với phiên bản cũ:
- Không raise RuntimeError nếu PDF thất bại → cho phép lưu docx-only
- Transaction chỉ bao quanh phần DB write, không bao quanh I/O render
- Trả IssuedDocument kể cả khi pdf_file = None
  (view sẽ phân biệt qua issued.pdf_file để hiện warning hoặc success)

Fix bug (v5→v6):
- tmp_docx_path KHÔNG bị xóa trước khi LibreOffice dùng nó
  (finally của Phase 1 cũ xóa file trước Phase 2 → LibreOffice báo "Docx không tồn tại")
- Dọn cả 2 tmp file trong finally của Phase 2 sau khi convert xong
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from apps.contract.models.document import DocumentTemplate, IssuedDocument
from apps.contract.models.quotation import QuotationDraft
from apps.contract.services.docx_renderer import render_quotation_docx
from apps.contract.services.document_payloads import (
    build_quotation_document_payload,
    build_quotation_preview_context,
)
from apps.contract.services.pdf_converter import build_pdf_bytes
from apps.contract.services.template_registry import get_active_document_template

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_latest_issued_quotation_document(quotation: QuotationDraft):
    return quotation.issued_documents.order_by("-version", "-issued_at", "-id").first()


def _next_issued_version(quotation: QuotationDraft) -> int:
    latest = get_latest_issued_quotation_document(quotation)
    if not latest:
        return 1
    return int(latest.version or 0) + 1


def _build_filenames(quotation: QuotationDraft, version: int) -> tuple[str, str]:
    slug = (
        slugify(quotation.company_name or f"quotation-{quotation.pk}")
        or f"quotation-{quotation.pk}"
    )
    base = f"{slug}-quotation-{quotation.pk}-v{version}"
    return f"{base}.docx", f"{base}.pdf"


def _issued_tmp_dir() -> Path:
    tmp_dir = Path(settings.MEDIA_ROOT) / "_tmp" / "contract" / "quotations"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def _tmp_work_paths(quotation: QuotationDraft, version: int) -> tuple[Path, Path]:
    base_slug = (
        slugify(quotation.company_name or f"quotation-{quotation.pk}")
        or f"quotation-{quotation.pk}"
    )
    unique = uuid.uuid4().hex[:12]
    base_name = f"{base_slug}-quotation-{quotation.pk}-v{version}-{unique}"
    tmp_dir = _issued_tmp_dir()
    return tmp_dir / f"{base_name}.docx", tmp_dir / f"{base_name}.pdf"


def _safe_unlink(*paths: Path) -> None:
    """Xóa file an toàn, bỏ qua nếu không tồn tại."""
    for p in paths:
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

def issue_quotation_document(
    *,
    quotation: QuotationDraft,
    actor=None,
    request=None,
) -> IssuedDocument:
    """
    Render docx, thử convert sang PDF, rồi lưu IssuedDocument.

    - Nếu PDF thành công  → issued.pdf_file có giá trị
    - Nếu PDF thất bại    → issued.pdf_file = None, chỉ có docx
      (view dùng issued.pdf_file để quyết định hiện success hay warning)

    Raise exception chỉ khi không thể render ra docx (lỗi template / I/O nghiêm trọng).
    """
    payload = build_quotation_document_payload(quotation)
    preview_context = build_quotation_preview_context(quotation)

    template = get_active_document_template(DocumentTemplate.DOC_TYPE_QUOTATION)
    version = _next_issued_version(quotation)

    tmp_docx_path, tmp_pdf_path = _tmp_work_paths(quotation, version)

    docx_bytes: bytes | None = None
    pdf_bytes: bytes | None = None

    # ── Phase 1: Render docx ──────────────────────────────────────────────────
    # QUAN TRỌNG: KHÔNG xóa tmp_docx_path ở đây.
    # Phase 2 cần file vật lý này để LibreOffice đọc và convert sang PDF.
    try:
        template_path = (
            template.docx_file.path
            if template and template.docx_file
            else None
        )

        render_quotation_docx(
            payload=payload,
            output_path=str(tmp_docx_path),
            template_path=template_path,
        )

        docx_bytes = tmp_docx_path.read_bytes()
        if not docx_bytes:
            raise RuntimeError("Render docx thành công nhưng file rỗng.")

    except Exception:
        # Nếu render docx thất bại hoàn toàn → dọn file rồi re-raise
        _safe_unlink(tmp_docx_path, tmp_pdf_path)
        raise

    # ── Phase 2: Convert sang PDF ─────────────────────────────────────────────
    # tmp_docx_path vẫn còn trên disk ở đây để LibreOffice đọc.
    # Dọn cả 2 tmp file trong finally SAU KHI convert xong.
    try:
        html_context = dict(preview_context)
        html_context["quotation"] = quotation
        html_context["today"] = date.today()
        fallback_html = render_to_string(
            "contract/staff/quotation_pdf.html",
            html_context,
            request=request,
        )

        base_url = request.build_absolute_uri("/") if request else None
        pdf_bytes = build_pdf_bytes(
            docx_path=str(tmp_docx_path),
            fallback_html=fallback_html,
            base_url=base_url,
            prefer_html=True,
        )

        if not pdf_bytes:
            logger.warning(
                "Không tạo được PDF cho quotation #%s v%s. "
                "Chỉ lưu docx. Kiểm tra LibreOffice hoặc cài WeasyPrint.",
                quotation.pk,
                version,
            )

    except Exception as exc:
        logger.warning(
            "Lỗi khi chuyển đổi PDF quotation #%s: %s",
            quotation.pk,
            exc,
        )
        pdf_bytes = None

    finally:
        # Dọn cả 2 tmp file SAU KHI LibreOffice đã convert xong
        _safe_unlink(tmp_docx_path, tmp_pdf_path)

    # ── Phase 3: Ghi DB (trong transaction) ──────────────────────────────────
    with transaction.atomic():
        IssuedDocument.objects.filter(
            quotation=quotation,
            doc_type=IssuedDocument.DOC_TYPE_QUOTATION,
            status=IssuedDocument.STATUS_ISSUED,
        ).update(status=IssuedDocument.STATUS_SUPERSEDED)

        docx_name, pdf_name = _build_filenames(quotation, version)

        issued = IssuedDocument(
            doc_type=IssuedDocument.DOC_TYPE_QUOTATION,
            status=IssuedDocument.STATUS_ISSUED,
            quotation=quotation,
            template=template,
            version=version,
            payload_json=payload,
            issued_at=timezone.now(),
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )

        issued.docx_file.save(docx_name, ContentFile(docx_bytes), save=False)

        if pdf_bytes:
            issued.pdf_file.save(pdf_name, ContentFile(pdf_bytes), save=False)
        # pdf_file sẽ là None/blank nếu không có pdf_bytes

        issued.save()

    return issued
