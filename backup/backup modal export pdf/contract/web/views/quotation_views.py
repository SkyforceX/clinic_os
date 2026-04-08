import json
import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.http import FileResponse, Http404, HttpResponse

from apps.contract.policies import ContractPolicy
from apps.contract.models.document import IssuedDocument
from apps.contract.models.quotation import QuotationDraft, QuotationLine
from apps.contract.services.document_payloads import build_quotation_preview_context
from apps.contract.services.quotation_documents import (
    get_latest_issued_quotation_document,
    issue_quotation_document,
)
from apps.organizations.services.company_commands import upsert_company_from_quotation
from apps.contract.models import CorporateContractProfile

# ── catalog ──────────────────────────────────────────────────────────────────

_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "..",
    "static",
    "contract",
    "data",
    "catalog.json",
)

def _quotation_queryset_for_user(user):
    qs = QuotationDraft.objects.select_related(
        "created_by",
        "company",
        "corporate_contract_profile__contract",
    )
    if ContractPolicy.is_manager(user):
        return qs
    return qs.filter(created_by=user)


def _get_quotation_for_user_or_404(user, quotation_id):
    return get_object_or_404(_quotation_queryset_for_user(user), pk=quotation_id)


def _latest_quotation_ids_by_company():
    return {
        q.company_id: q.id
        for q in (
            QuotationDraft.objects
            .filter(company__isnull=False)
            .order_by("company_id", "-created_at", "-id")
            .distinct("company_id")
        )
    }


def _decorate_quotation_contract_state(quotation):
    linked_profile = getattr(quotation, "corporate_contract_profile", None)
    linked_contract = getattr(linked_profile, "contract", None) if linked_profile else None
    quotation.linked_contract = linked_contract
    quotation.has_contract = linked_contract is not None
    quotation.is_latest_for_company = False

    latest_map = _latest_quotation_ids_by_company()
    if quotation.company_id:
        quotation.is_latest_for_company = latest_map.get(quotation.company_id) == quotation.id

    return quotation


def _load_catalog():
    with open(os.path.abspath(_CATALOG_PATH), "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, list):
        catalog = raw
    elif isinstance(raw, dict):
        catalog = raw.get("catalog") or raw.get("items") or []
    else:
        catalog = []

    normalized = []
    for item in catalog:
        if isinstance(item, dict):
            normalized.append(item)

    return normalized


def _group_catalog(catalog):
    groups = {}
    for item in catalog:
        if not isinstance(item, dict):
            continue

        group = item.get("group") or "Khác"
        subgroup = item.get("subgroup") or ""

        groups.setdefault(
            group,
            {
                "items": [],
                "subgroups": {},
            },
        )

        if subgroup:
            groups[group]["subgroups"].setdefault(subgroup, []).append(item)
        else:
            groups[group]["items"].append(item)

    return groups


def _safe_decimal(raw):
    if raw in (None, "", "None"):
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _safe_int(raw, default=0):
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return default


def _fmt_vnd(v):
    if v in (None, "", 0):
        return "0"
    return f"{int(v):,}".replace(",", ".")


def _file_response(field_file):
    if not field_file or not field_file.name:
        raise Http404("Tệp chưa được tạo.")
    filename = os.path.basename(field_file.name)
    return FileResponse(field_file.open("rb"), as_attachment=True, filename=filename)


# ── list ─────────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def quotation_list(request):
    quotations = list(
        _quotation_queryset_for_user(request.user)
        .order_by("-created_at")
    )

    latest_map = _latest_quotation_ids_by_company()
    for q in quotations:
        linked_profile = getattr(q, "corporate_contract_profile", None)
        linked_contract = getattr(linked_profile, "contract", None) if linked_profile else None
        q.linked_contract = linked_contract
        q.has_contract = linked_contract is not None
        q.is_latest_for_company = bool(q.company_id and latest_map.get(q.company_id) == q.id)

    return render(
        request,
        "contract/staff/quotation_list.html",
        {
            "quotations": quotations,
            "is_manager": ContractPolicy.is_manager(request.user),
        },
    )


# ── create form ──────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def edit_quotation(request, quotation_id):
    quotation = _get_quotation_for_user_or_404(request.user, quotation_id)
    quotation = _decorate_quotation_contract_state(quotation)

    if quotation.is_locked:
        messages.error(request, "Báo giá này đã bị khóa.")
        return redirect("contract:quotation_preview", quotation_id=quotation.id)

    if quotation.has_contract:
        messages.error(request, "Báo giá này đã phát sinh hợp đồng nên không thể sửa trực tiếp.")
        return redirect("contract:quotation_preview", quotation_id=quotation.id)

    catalog = _load_catalog()
    groups = _group_catalog(catalog)

    # Map catalog_id → dữ liệu line đã lưu, để JS pre-fill form
    existing_lines = {}
    for line in quotation.lines.order_by("display_order"):
        if line.catalog_id is None:
            continue
        existing_lines[str(line.catalog_id)] = {
            "selected": True,
            "checked_male": bool(line.checked_male),
            "checked_fs": bool(line.checked_female_single),
            "checked_ff": bool(line.checked_female_family),
            "price_male": int(line.price_male or 0),
            "price_fs": int(line.price_female_single or 0),
            "price_ff": int(line.price_female_family or 0),
            "udai_male": int(line.udai_price_male or 0),
            "udai_fs": int(line.udai_price_fs or 0),
            "udai_ff": int(line.udai_price_ff or 0),
            "pct_male": float(line.discount_male_pct or 0),
            "pct_fs": float(line.discount_fs_pct or 0),
            "pct_ff": float(line.discount_ff_pct or 0),
        }

    return render(
        request,
        "contract/staff/edit_quotation.html",
        {
            "quotation": quotation,
            "groups": groups,
            "catalog_json": json.dumps(catalog, ensure_ascii=False),
            "existing_lines_json": json.dumps(existing_lines, ensure_ascii=False),
        },
    )


@login_required(login_url="authentication:staff_login")
def create_proposal(request):
    catalog = _load_catalog()
    groups = _group_catalog(catalog)
    default_valid_until = (date.today() + timedelta(days=30)).isoformat()

    return render(
        request,
        "contract/staff/create_proposal.html",
        {
            "groups": groups,
            "catalog_json": json.dumps(catalog, ensure_ascii=False),
            "default_valid_until": default_valid_until,
        },
    )


# ── save ─────────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
@transaction.atomic
def save_quotation(request):
    post = request.POST

    company_name = (post.get("company_name") or "").strip()
    if not company_name:
        messages.error(request, "Vui lòng nhập tên công ty.")
        return redirect("contract:create_proposal")
    
    quotation_id = post.get("quotation_id")
    if quotation_id:
        quotation = _get_quotation_for_user_or_404(request.user, quotation_id)
        quotation = _decorate_quotation_contract_state(quotation)
        
        if quotation.is_locked:
            messages.error(request, "Báo giá này đã bị khóa.")
            return redirect("contract:quotation_preview", quotation_id=quotation.id)
        
        if quotation.has_contract:
            messages.error(request, "Báo giá này đã phát sinh hợp đồng nên không thể sửa.")
            return redirect("contract:quotation_preview", quotation_id=quotation.id)
        
        quotation.lines.all().delete()
    else:
        quotation = QuotationDraft()
    
    company_address = (post.get("company_address") or "").strip()
    
    company = upsert_company_from_quotation(
        actor=request.user,
        name=company_name,
        address=company_address,
        company=quotation.company if quotation.pk else None,
    )
    
    quotation.created_by = request.user
    quotation.company = company
    
    # snapshot preview/pdf/docx cũ
    quotation.company_name = company.name
    quotation.company_address = company.address or ""
    
    quotation.contact_name = (post.get("contact_name") or "").strip()
    quotation.note = (post.get("note") or "").strip()

    try:
        quotation.valid_until = date.fromisoformat(post.get("valid_until") or "")
    except (ValueError, TypeError):
        quotation.valid_until = date.today() + timedelta(days=30)

    quotation.pax_from = _safe_int(post.get("pax_from"), 0) or None
    quotation.male_count = _safe_int(post.get("male_count"), 0)
    quotation.female_single_count = _safe_int(post.get("female_single_count"), 0)
    quotation.female_family_count = _safe_int(post.get("female_family_count"), 0)

    # Giảm giá toàn cục (toolbar)
    quotation.discount_male_pct = _safe_decimal(post.get("discount_male_pct")) or 0
    quotation.discount_fs_pct   = _safe_decimal(post.get("discount_fs_pct")) or 0
    quotation.discount_ff_pct   = _safe_decimal(post.get("discount_ff_pct")) or 0
    quotation.save()

    catalog = _load_catalog()
    catalog_map = {str(item["id"]): item for item in catalog if isinstance(item, dict) and "id" in item}

    lines = []
    selected_ids = post.getlist("selected_ids")

    for order, cid in enumerate(selected_ids):
        cat = catalog_map.get(str(cid))
        if not cat:
            continue

        checked_male = f"checked_male_{cid}" in post
        checked_fs = f"checked_fs_{cid}" in post
        checked_ff = f"checked_ff_{cid}" in post

        if not (checked_male or checked_fs or checked_ff):
            continue

        def price_val(key):
            raw = post.get(f"price_{key}_{cid}")
            d = _safe_decimal(raw)
            if d is None:
                fallback = cat.get(f"price_{key}")
                return _safe_decimal(fallback)
            return d

        line = QuotationLine(
            quotation=quotation,
            catalog_id=int(cid),
            item_name=cat.get("name", ""),
            description=cat.get("description", ""),
            group_name=cat.get("group", ""),
            subgroup_name=cat.get("subgroup") or "",
            list_price=_safe_decimal(cat.get("list_price")),
            # Giá ưu đãi (sau toolbar, trước row %)
            udai_price_male=_safe_decimal(post.get(f"udai_male_{cid}")) if checked_male else None,
            udai_price_fs=_safe_decimal(post.get(f"udai_fs_{cid}")) if checked_fs else None,
            udai_price_ff=_safe_decimal(post.get(f"udai_ff_{cid}")) if checked_ff else None,
            # % giảm từng dòng
            discount_male_pct=_safe_decimal(post.get(f"pct_male_{cid}")) or 0,
            discount_fs_pct=_safe_decimal(post.get(f"pct_fs_{cid}")) or 0,
            discount_ff_pct=_safe_decimal(post.get(f"pct_ff_{cid}")) or 0,
            # Giá cuối cùng (computed by JS, submitted as hidden)
            price_male=price_val("male") if checked_male else None,
            price_female_single=price_val("female_single") if checked_fs else None,
            price_female_family=price_val("female_family") if checked_ff else None,
            checked_male=checked_male,
            checked_female_single=checked_fs,
            checked_female_family=checked_ff,
            price_type=cat.get("price_type", "standard"),
            note=cat.get("note") or "",
            display_order=order,
        )
        lines.append(line)

    if not lines:
        quotation.delete()
        messages.error(request, "Chưa chọn dịch vụ nào.")
        return redirect("contract:create_proposal")

    QuotationLine.objects.bulk_create(lines)
    messages.success(request, "Đã lưu báo giá.")
    return redirect("contract:quotation_preview", quotation_id=quotation.pk)


# ── preview ──────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def quotation_preview(request, quotation_id):
    quotation = _get_quotation_for_user_or_404(request.user, quotation_id)
    quotation = _decorate_quotation_contract_state(quotation)

    context = build_quotation_preview_context(quotation)
    context["quotation"] = quotation
    context["latest_issued"] = get_latest_issued_quotation_document(quotation)
    context["linked_contract"] = quotation.linked_contract
    context["can_edit_quotation"] = (not quotation.is_locked) and (not quotation.has_contract)
    context["can_issue_document"] = not quotation.is_locked
    return render(request, "contract/staff/quotation_preview.html", context)


# ── issue docx/pdf ───────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def issue_quotation_document_view(request, quotation_id):
    quotation = _get_quotation_for_user_or_404(request.user, quotation_id)
    quotation = _decorate_quotation_contract_state(quotation)

    if quotation.is_locked:
        messages.error(request, "Báo giá đã bị khóa, không thể phát hành lại tài liệu.")
        return redirect("contract:quotation_preview", quotation_id=quotation.pk)

    try:
        issued = issue_quotation_document(
            quotation=quotation,
            actor=request.user,
            request=request,
        )
    except Exception as exc:
        messages.error(request, f"Không thể phát hành tài liệu: {exc}")
        return redirect("contract:quotation_preview", quotation_id=quotation.pk)

    if issued.pdf_file:
        messages.success(request, "Đã phát hành báo giá PDF.")
    else:
        messages.warning(
            request,
            "PDF chưa được tạo, đang dùng fallback hoặc thiếu công cụ chuyển đổi.",
        )

    return redirect("contract:quotation_preview", quotation_id=quotation.pk)


@login_required(login_url="authentication:staff_login")
def download_issued_quotation_docx(request, issued_id):
    issued = get_object_or_404(
        IssuedDocument,
        pk=issued_id,
        doc_type=IssuedDocument.DOC_TYPE_QUOTATION,
    )
    return _file_response(issued.docx_file)


@login_required(login_url="authentication:staff_login")
def download_issued_quotation_pdf(request, issued_id):
    issued = get_object_or_404(
        IssuedDocument,
        pk=issued_id,
        doc_type=IssuedDocument.DOC_TYPE_QUOTATION,
    )
    return _file_response(issued.pdf_file)


# ── pdf export fallback / compatibility ──────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def quotation_pdf(request):
    quotation_id = request.GET.get("id")
    quotation = _get_quotation_for_user_or_404(request.user, quotation_id)

    latest_issued = get_latest_issued_quotation_document(quotation)
    if latest_issued and latest_issued.pdf_file:
        return _file_response(latest_issued.pdf_file)

    context = build_quotation_preview_context(quotation)
    context["quotation"] = quotation
    context["today"] = date.today()

    html_string = render_to_string(
        "contract/staff/quotation_pdf.html",
        context,
        request=request,
    )

    try:
        import weasyprint

        pdf_bytes = weasyprint.HTML(
            string=html_string,
            base_url=request.build_absolute_uri("/"),
        ).write_pdf()

        filename = f"bao-gia-{quotation.company_name}-{quotation.pk}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        return HttpResponse(html_string, content_type="text/html; charset=utf-8")


# ── delete ───────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def delete_quotation(request, pk):
    quotation = _get_quotation_for_user_or_404(request.user, pk)
    quotation = _decorate_quotation_contract_state(quotation)

    if quotation.has_contract:
        messages.error(request, "Báo giá này đã phát sinh hợp đồng nên không thể xóa.")
        return redirect("contract:quotation_preview", quotation_id=quotation.id)

    if quotation.is_locked:
        messages.error(request, "Báo giá này đã bị khóa nên không thể xóa.")
        return redirect("contract:quotation_preview", quotation_id=quotation.id)

    if request.method == "POST":
        quotation.delete()
        messages.success(request, "Đã xóa báo giá.")
        return redirect("contract:quotation_list")

    return render(
        request,
        "contract/staff/quotation_confirm_delete.html",
        {"quotation": quotation},
    )