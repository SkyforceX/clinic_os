"""
contract_documents.py
----------------------
Phát hành (issue) hợp đồng KSK doanh nghiệp dưới dạng docx + pdf.

Mirror hoàn toàn cơ chế của quotation_documents.py:
- Phase 1 : Render docx từ template (hoặc fallback)
- Phase 2 : Convert sang PDF qua LibreOffice (hoặc WeasyPrint)
- Phase 3 : Ghi IssuedDocument vào DB (atomic), supersede bản cũ

Đặt tại: apps/contract/services/contract_documents.py
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.template.loader import render_to_string

from apps.contract.models.contract import Contract
from apps.contract.models.document import DocumentTemplate, IssuedDocument
from apps.contract.services.document_payloads import (
    build_contract_document_payload,
    build_contract_preview_context,
)
from apps.contract.services.docx_renderer import render_contract_docx
from apps.contract.services.pdf_converter import build_pdf_bytes
from apps.contract.services.template_registry import get_active_document_template

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _resolve_base_url(request=None) -> str | None:
    if request is not None:
        try:
            return request.build_absolute_uri("/")
        except Exception:
            pass
    return getattr(settings, "PUBLIC_BASE_URL", None)


def get_latest_issued_contract_document(contract: Contract):
    """Lấy IssuedDocument mới nhất của hợp đồng (theo version)."""
    return (
        contract.issued_documents
        .filter(doc_type=IssuedDocument.DOC_TYPE_CONTRACT)
        .order_by("-version", "-issued_at", "-id")
        .first()
    )


def _next_issued_version(contract: Contract) -> int:
    latest = get_latest_issued_contract_document(contract)
    if not latest:
        return 1
    return int(latest.version or 0) + 1


def _build_filenames(contract: Contract, version: int) -> tuple[str, str]:
    profile = getattr(contract, "corporate_profile", None)
    company_raw = (
        profile.company_name_snapshot
        if profile and profile.company_name_snapshot
        else f"contract-{contract.pk}"
    )
    slug = slugify(company_raw) or f"contract-{contract.pk}"
    base = f"{slug}-contract-{contract.pk}-v{version}"
    return f"{base}.docx", f"{base}.pdf"


def _tmp_dir() -> Path:
    tmp_dir = Path(settings.MEDIA_ROOT) / "_tmp" / "contract" / "contracts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def _tmp_work_paths(contract: Contract, version: int) -> tuple[Path, Path]:
    profile = getattr(contract, "corporate_profile", None)
    company_raw = (
        profile.company_name_snapshot
        if profile and profile.company_name_snapshot
        else f"contract-{contract.pk}"
    )
    slug = slugify(company_raw) or f"contract-{contract.pk}"
    unique = uuid.uuid4().hex[:12]
    base = f"{slug}-contract-{contract.pk}-v{version}-{unique}"
    tmp_dir = _tmp_dir()
    return tmp_dir / f"{base}.docx", tmp_dir / f"{base}.pdf"


def _safe_unlink(*paths: Path) -> None:
    for p in paths:
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# ── Main service ─────────────────────────────────────────────────────────────

def issue_contract_document(
    *,
    contract: Contract,
    actor=None,
    request=None,
) -> IssuedDocument:
    """
    Render hợp đồng → docx, convert → PDF, lưu IssuedDocument.

    - Nếu PDF thành công  → issued.pdf_file có giá trị
    - Nếu PDF thất bại    → issued.pdf_file = None, chỉ có docx
    - Raise exception chỉ khi render docx thất bại hoàn toàn

    Args:
        contract : Contract instance (cần có corporate_profile, blood_collection_schedules)
        actor    : User đang thực hiện phát hành
        request  : HttpRequest (dùng để build_absolute_uri cho fallback HTML)
    """
    # ── Chuẩn bị ────────────────────────────────────────────────────────────
    # Eager load relations cần cho payload
    if not hasattr(contract, "_corporate_profile_cached"):
        contract = (
            Contract.objects
            .select_related("corporate_profile__quotation", "company")
            .prefetch_related(
                "blood_collection_schedules",
                "corporate_profile__quotation__lines",
            )
            .get(pk=contract.pk)
        )

    payload = build_contract_document_payload(contract)
    preview_context = build_contract_preview_context(contract)
    template = get_active_document_template(DocumentTemplate.DOC_TYPE_CONTRACT)
    version = _next_issued_version(contract)
    tmp_docx_path, tmp_pdf_path = _tmp_work_paths(contract, version)

    docx_bytes: bytes | None = None
    pdf_bytes: bytes | None = None

    # ── Phase 1: Render docx ─────────────────────────────────────────────────
    # KHÔNG xóa tmp_docx_path ở đây — Phase 2 cần file vật lý cho LibreOffice
    try:
        template_path = (
            template.docx_file.path
            if template and template.docx_file
            else None
        )

        render_contract_docx(
            payload=payload,
            output_path=str(tmp_docx_path),
            template_path=template_path,
        )

        docx_bytes = tmp_docx_path.read_bytes()
        if not docx_bytes:
            raise RuntimeError("Render docx hợp đồng thành công nhưng file rỗng.")

    except Exception:
        _safe_unlink(tmp_docx_path, tmp_pdf_path)
        raise

    # ── Phase 2: Convert sang PDF ────────────────────────────────────────────
    try:
        html_context = dict(preview_context)
        
        fallback_html = render_to_string(
            "contract/staff/corporate_contract_pdf.html",
            html_context,
            request=request,
        )
        
        base_url = _resolve_base_url(request)
        pdf_bytes = build_pdf_bytes(
            docx_path=str(tmp_docx_path),
            fallback_html=fallback_html,
            base_url=base_url,
            prefer_html=False,
        )
        
        if not pdf_bytes:
            logger.warning(
                "Không tạo được PDF cho contract #%s v%s. "
                "Chỉ lưu docx. Kiểm tra LibreOffice hoặc cài WeasyPrint.",
                contract.pk,
                version,
            )

    except Exception as exc:
        logger.warning("Lỗi khi convert PDF contract #%s: %s", contract.pk, exc)
        pdf_bytes = None

    finally:
        # Dọn 2 tmp file SAU KHI LibreOffice đã dùng xong
        _safe_unlink(tmp_docx_path, tmp_pdf_path)

    # ── Phase 3: Ghi DB (atomic) ──────────────────────────────────────────────
    with transaction.atomic():
        # Supersede các bản ISSUED cũ của hợp đồng này
        IssuedDocument.objects.filter(
            contract=contract,
            doc_type=IssuedDocument.DOC_TYPE_CONTRACT,
            status=IssuedDocument.STATUS_ISSUED,
        ).update(status=IssuedDocument.STATUS_SUPERSEDED)

        docx_name, pdf_name = _build_filenames(contract, version)

        issued = IssuedDocument(
            doc_type=IssuedDocument.DOC_TYPE_CONTRACT,
            status=IssuedDocument.STATUS_ISSUED,
            contract=contract,
            quotation=None,                      # Contract document không gắn quotation
            template=template,
            version=version,
            payload_json=payload,
            issued_at=timezone.now(),
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )

        issued.docx_file.save(docx_name, ContentFile(docx_bytes), save=False)

        if pdf_bytes:
            issued.pdf_file.save(pdf_name, ContentFile(pdf_bytes), save=False)

        issued.save()

    logger.info(
        "Đã phát hành IssuedDocument #%s (contract #%s, v%s, pdf=%s)",
        issued.pk,
        contract.pk,
        version,
        bool(pdf_bytes),
    )

    return issued
