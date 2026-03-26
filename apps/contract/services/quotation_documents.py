import os
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


def get_latest_issued_quotation_document(quotation: QuotationDraft):
    return quotation.issued_documents.order_by("-version", "-issued_at", "-id").first()


def _next_issued_version(quotation: QuotationDraft) -> int:
    latest = get_latest_issued_quotation_document(quotation)
    if not latest:
        return 1
    return int(latest.version or 0) + 1


def _build_filenames(quotation: QuotationDraft, version: int) -> tuple[str, str]:
    slug = slugify(quotation.company_name or f"quotation-{quotation.pk}") or f"quotation-{quotation.pk}"
    base = f"{slug}-quotation-{quotation.pk}-v{version}"
    return f"{base}.docx", f"{base}.pdf"


def _issued_tmp_dir() -> Path:
    tmp_dir = Path(settings.MEDIA_ROOT) / "_tmp" / "contract" / "quotations"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def _tmp_work_paths(quotation: QuotationDraft, version: int) -> tuple[Path, Path]:
    base_slug = slugify(quotation.company_name or f"quotation-{quotation.pk}") or f"quotation-{quotation.pk}"
    unique = uuid.uuid4().hex[:12]
    base_name = f"{base_slug}-quotation-{quotation.pk}-v{version}-{unique}"
    tmp_dir = _issued_tmp_dir()
    return tmp_dir / f"{base_name}.docx", tmp_dir / f"{base_name}.pdf"


@transaction.atomic
def issue_quotation_document(*, quotation: QuotationDraft, actor=None, request=None):
    payload = build_quotation_document_payload(quotation)
    preview_context = build_quotation_preview_context(quotation)

    template = get_active_document_template(DocumentTemplate.DOC_TYPE_QUOTATION)
    version = _next_issued_version(quotation)

    IssuedDocument.objects.filter(
        quotation=quotation,
        doc_type=IssuedDocument.DOC_TYPE_QUOTATION,
        status=IssuedDocument.STATUS_ISSUED,
    ).update(status=IssuedDocument.STATUS_SUPERSEDED)

    tmp_docx_path, tmp_pdf_path = _tmp_work_paths(quotation, version)
    docx_bytes = None
    pdf_bytes = None

    try:
        template_path = template.docx_file.path if template and template.docx_file else None

        render_quotation_docx(
            payload=payload,
            output_path=str(tmp_docx_path),
            template_path=template_path,
        )

        docx_bytes = tmp_docx_path.read_bytes()

        html_context = dict(preview_context)
        html_context["quotation"] = quotation
        html_context["today"] = date.today()
        fallback_html = render_to_string(
            "contract/staff/proposal_pdf.html",
            html_context,
            request=request,
        )

        base_url = request.build_absolute_uri("/") if request else None
        pdf_bytes = build_pdf_bytes(
            docx_path=str(tmp_docx_path),
            fallback_html=fallback_html,
            base_url=base_url,
        )

        if not pdf_bytes:
            raise RuntimeError(
                "Không tạo được PDF. Kiểm tra LibreOffice/WeasyPrint, quyền ghi MEDIA_ROOT, và tài khoản chạy service."
            )

    finally:
        if tmp_docx_path.exists():
            try:
                tmp_docx_path.unlink()
            except OSError:
                pass

        if tmp_pdf_path.exists():
            try:
                tmp_pdf_path.unlink()
            except OSError:
                pass

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
    issued.pdf_file.save(pdf_name, ContentFile(pdf_bytes), save=False)
    issued.save()

    return issued