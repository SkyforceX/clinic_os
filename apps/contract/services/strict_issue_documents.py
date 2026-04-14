from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.contract.models import Contract
from apps.contract.models.document import DocumentTemplate, IssuedDocument
from apps.contract.models.quotation import QuotationDraft
from apps.contract.services.contract_documents import get_latest_issued_contract_document
from apps.contract.services.docx_renderer import render_contract_docx, render_quotation_docx
from apps.contract.services.document_payloads import (
    build_contract_document_payload,
    build_quotation_document_payload,
)
from apps.contract.services.pdf_converter import convert_docx_to_pdf_via_office
from apps.contract.services.quotation_documents import get_latest_issued_quotation_document
from apps.contract.services.template_registry import get_active_document_template

logger = logging.getLogger(__name__)


def _tmp_dir(*parts: str) -> Path:
    path = Path(settings.MEDIA_ROOT) / "_tmp" / "contract"
    for part in parts:
        path /= part
    path.mkdir(parents=True, exist_ok=True)
    return path


def _tmp_paths(base_slug: str, object_id: int, version: int, folder: str, suffix: str) -> tuple[Path, Path]:
    unique = uuid.uuid4().hex[:12]
    base = f"{base_slug}-{suffix}-{object_id}-v{version}-{unique}"
    tmp_root = _tmp_dir(folder)
    return tmp_root / f"{base}.docx", tmp_root / f"{base}.pdf"


def _safe_unlink(*paths: Path) -> None:
    for path in paths:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def issue_quotation_document_strict(*, quotation: QuotationDraft, actor=None) -> IssuedDocument:
    payload = build_quotation_document_payload(quotation)
    template = get_active_document_template(DocumentTemplate.DOC_TYPE_QUOTATION)
    latest = get_latest_issued_quotation_document(quotation)
    version = 1 if not latest else int(latest.version or 0) + 1
    slug = slugify(quotation.company_name or f"quotation-{quotation.pk}") or f"quotation-{quotation.pk}"
    tmp_docx_path, tmp_pdf_path = _tmp_paths(slug, quotation.pk, version, "quotations", "quotation")

    template_path = template.docx_file.path if template and template.docx_file else None

    try:
        render_quotation_docx(
            payload=payload,
            output_path=str(tmp_docx_path),
            template_path=template_path,
        )
        docx_bytes = tmp_docx_path.read_bytes()
        if not docx_bytes:
            raise RuntimeError("Render docx bao gia thanh cong nhung file rong.")
        pdf_bytes = convert_docx_to_pdf_via_office(str(tmp_docx_path), strict=True)
    finally:
        _safe_unlink(tmp_docx_path, tmp_pdf_path)

    with transaction.atomic():
        IssuedDocument.objects.filter(
            quotation=quotation,
            doc_type=IssuedDocument.DOC_TYPE_QUOTATION,
            status=IssuedDocument.STATUS_ISSUED,
        ).update(status=IssuedDocument.STATUS_SUPERSEDED)

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
        base = f"{slug}-quotation-{quotation.pk}-v{version}"
        issued.docx_file.save(f"{base}.docx", ContentFile(docx_bytes), save=False)
        issued.pdf_file.save(f"{base}.pdf", ContentFile(pdf_bytes), save=False)
        issued.save()
        return issued


def issue_contract_document_strict(*, contract: Contract, actor=None) -> IssuedDocument:
    contract = (
        Contract.objects
        .select_related("corporate_profile__quotation", "company")
        .prefetch_related("blood_collection_schedules", "corporate_profile__quotation__lines")
        .get(pk=contract.pk)
    )
    payload = build_contract_document_payload(contract)
    template = get_active_document_template(DocumentTemplate.DOC_TYPE_CONTRACT)
    latest = get_latest_issued_contract_document(contract)
    version = 1 if not latest else int(latest.version or 0) + 1

    profile = getattr(contract, "corporate_profile", None)
    company_raw = (
        profile.company_name_snapshot
        if profile and profile.company_name_snapshot
        else f"contract-{contract.pk}"
    )
    slug = slugify(company_raw) or f"contract-{contract.pk}"
    tmp_docx_path, tmp_pdf_path = _tmp_paths(slug, contract.pk, version, "contracts", "contract")
    template_path = template.docx_file.path if template and template.docx_file else None

    try:
        render_contract_docx(
            payload=payload,
            output_path=str(tmp_docx_path),
            template_path=template_path,
        )
        docx_bytes = tmp_docx_path.read_bytes()
        if not docx_bytes:
            raise RuntimeError("Render docx hop dong thanh cong nhung file rong.")
        pdf_bytes = convert_docx_to_pdf_via_office(str(tmp_docx_path), strict=True)
    finally:
        _safe_unlink(tmp_docx_path, tmp_pdf_path)

    with transaction.atomic():
        IssuedDocument.objects.filter(
            contract=contract,
            doc_type=IssuedDocument.DOC_TYPE_CONTRACT,
            status=IssuedDocument.STATUS_ISSUED,
        ).update(status=IssuedDocument.STATUS_SUPERSEDED)

        issued = IssuedDocument(
            doc_type=IssuedDocument.DOC_TYPE_CONTRACT,
            status=IssuedDocument.STATUS_ISSUED,
            contract=contract,
            template=template,
            version=version,
            payload_json=payload,
            issued_at=timezone.now(),
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        base = f"{slug}-contract-{contract.pk}-v{version}"
        issued.docx_file.save(f"{base}.docx", ContentFile(docx_bytes), save=False)
        issued.pdf_file.save(f"{base}.pdf", ContentFile(pdf_bytes), save=False)
        issued.save()
        return issued
