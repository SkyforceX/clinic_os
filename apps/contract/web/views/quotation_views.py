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
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.contract.policies import ContractPolicy
from apps.contract.models.document import IssuedDocument
from apps.contract.models.quotation import (
    QuotationDraft,
    QuotationLine,
    QuotationPackage,
    QuotationStatus,
    DEFAULT_PACKAGE_COLUMNS,
)
from apps.contract.services.document_payloads import build_quotation_preview_context
from apps.contract.services.pdf_converter import PdfConversionError, PdfConversionTimeoutError
from apps.contract.services.quotation_documents import (
    get_latest_issued_quotation_document,
)
from apps.contract.services.strict_issue_documents import issue_quotation_document_strict
from apps.organizations.services.company_commands import upsert_company_from_quotation
from apps.catalogs.models import CheckupCategory


def load_catalog():
    qs = (
        CheckupCategory.objects
        .filter(is_active=True)
        .select_related("group_checkup")
        .order_by("group_checkup__display_order", "group_checkup__name", "display_order", "id")
    )
    result = []
    for cat in qs:
        group = cat.group_checkup
        try:
            item_id = int(cat.item_code) if cat.item_code else cat.id
        except (ValueError, TypeError):
            item_id = cat.id
        result.append({
            "id":                  item_id,
            "group":               group.name,
            "group_en":            group.group_en or "",
            "subgroup":            cat.subgroup_name or None,
            "name":                cat.item_name,
            "description":         cat.description or "",
            "price_type":          cat.price_type,
            "list_price":          int(cat.list_price or 0),
            "price_male":          int(cat.price_male or 0),
            "price_female_single": int(cat.price_female_single or 0),
            "price_female_family": int(cat.price_female_family or 0),
            "for_male":            bool(cat.for_male),
            "for_female_single":   bool(cat.for_female_single),
            "for_female_family":   bool(cat.for_female_family),
            "note":                cat.note or "",
        })
    return result


def group_catalog(catalog):
    groups = {}
    for item in catalog:
        if not isinstance(item, dict):
            continue
        group    = item.get("group") or "Khác"
        subgroup = item.get("subgroup") or ""
        groups.setdefault(group, {"items": [], "subgroups": {}})
        if subgroup:
            groups[group]["subgroups"].setdefault(subgroup, []).append(item)
        else:
            groups[group]["items"].append(item)
    return groups


def quotation_queryset_for_user(user):
    qs = QuotationDraft.objects.select_related("created_by", "company", "corporate_contract_profile__contract")
    if ContractPolicy.is_manager(user):
        return qs
    return qs.filter(created_by=user)


def get_quotation_for_user_or_404(user, quotation_id):
    return get_object_or_404(quotation_queryset_for_user(user), pk=quotation_id)


def latest_quotation_ids_by_company():
    return {
        q.company_id: q.id
        for q in (
            QuotationDraft.objects
            .filter(company__isnull=False)
            .order_by("company_id", "-created_at", "-id")
            .distinct("company_id")
        )
    }


def decorate_quotation_contract_state(quotation):
    linked_profile  = getattr(quotation, "corporate_contract_profile", None)
    linked_contract = getattr(linked_profile, "contract", None) if linked_profile else None
    quotation.linked_contract = linked_contract
    quotation.has_contract    = linked_contract is not None
    quotation.is_latest_for_company = False
    latest_map = latest_quotation_ids_by_company()
    if quotation.company_id:
        quotation.is_latest_for_company = latest_map.get(quotation.company_id) == quotation.id
    return quotation


def quotation_issue_blocked_by_contract(quotation):
    linked_contract = getattr(quotation, "linked_contract", None)
    if not linked_contract:
        return False
    return bool(getattr(linked_contract, "is_locked", False) or getattr(linked_contract, "is_approved", False))


def safe_int(raw, default=0):
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return default


def safe_decimal(raw):
    if raw in (None, "", "None"):
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def fmt_vnd(v):
    if v in (None, "", 0):
        return "0"
    return f"{int(v):,}".replace(",", ".")


def file_response(field_file):
    if not field_file or not field_file.name:
        raise Http404("Tệp chưa được tạo.")
    filename = os.path.basename(field_file.name)
    return FileResponse(field_file.open("rb"), as_attachment=True, filename=filename)


# ── list ─────────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def quotation_list(request):
    quotations = list(quotation_queryset_for_user(request.user).order_by("-created_at"))
    latest_map = latest_quotation_ids_by_company()

    from apps.approvals.models import ApprovalRequest, ApprovalStatus
    quotation_ids = [q.pk for q in quotations]
    pending_map = {
        ar.quotation_id: ar
        for ar in ApprovalRequest.objects.filter(
            quotation_id__in=quotation_ids, status=ApprovalStatus.PENDING
        )
    }

    for q in quotations:
        linked_profile  = getattr(q, "corporate_contract_profile", None)
        linked_contract = getattr(linked_profile, "contract", None) if linked_profile else None
        q.linked_contract = linked_contract
        q.has_contract    = linked_contract is not None
        q.is_latest_for_company = bool(q.company_id and latest_map.get(q.company_id) == q.id)
        q.pending_ar = pending_map.get(q.pk)

    return render(request, "contract/staff/quotation_list.html", {
        "quotations": quotations,
        "is_manager": ContractPolicy.is_manager(request.user),
    })


# ── create form ───────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def create_proposal(request):
    catalog = load_catalog()
    groups  = group_catalog(catalog)
    default_valid_until = (date.today() + timedelta(days=30)).isoformat()

    package_templates_json = "[]"
    try:
        from pathlib import Path
        from django.conf import settings
        pt_path = Path(settings.BASE_DIR) / "apps" / "contract" / "static" / "contract" / "data" / "package_templates.json"
        if pt_path.exists():
            package_templates_json = pt_path.read_text(encoding="utf-8")
    except Exception:
        pass

    return render(request, "contract/staff/create_quotation.html", {
        "groups":                 groups,
        "catalog_json":           json.dumps(catalog, ensure_ascii=False),
        "default_valid_until":    default_valid_until,
        "package_templates_json": package_templates_json,
        "default_columns_json":   json.dumps(DEFAULT_PACKAGE_COLUMNS, ensure_ascii=False),
    })


# ── edit form ─────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def edit_quotation(request, quotation_id):
    quotation = get_quotation_for_user_or_404(request.user, quotation_id)
    quotation = decorate_quotation_contract_state(quotation)

    if quotation.is_locked:
        messages.error(request, "Báo giá này đã bị khóa.")
        return redirect("contract:quotation_preview", quotation_id=quotation.id)

    if quotation.has_contract:
        messages.error(request, "Báo giá này đã phát sinh hợp đồng nên không thể sửa trực tiếp.")
        return redirect("contract:quotation_preview", quotation_id=quotation.id)

    catalog = load_catalog()
    groups  = group_catalog(catalog)

    packages_qs = list(quotation.packages.prefetch_related("lines").order_by("display_order", "id"))

    if packages_qs:
        existing_packages = []
        for pkg in packages_qs:
            pkg_lines = []
            for line in pkg.lines.order_by("display_order"):
                pkg_lines.append({
                    "catalog_id":    line.catalog_id,
                    "checked_male":  bool(line.checked_male),
                    "checked_fs":    bool(line.checked_female_single),
                    "checked_ff":    bool(line.checked_female_family),
                    "price_male":    int(line.price_male or 0),
                    "price_fs":      int(line.price_female_single or 0),
                    "price_ff":      int(line.price_female_family or 0),
                    "udai_male":     int(line.udai_price_male or 0),
                    "udai_fs":       int(line.udai_price_fs or 0),
                    "udai_ff":       int(line.udai_price_ff or 0),
                    "pct_male":      float(line.discount_male_pct or 0),
                    "pct_fs":        float(line.discount_fs_pct or 0),
                    "pct_ff":        float(line.discount_ff_pct or 0),
                    "extra_prices":  line.extra_prices_json or {},
                    "for_m":         bool(line.for_male),
                    "for_fs":        bool(line.for_female_single),
                    "for_ff":        bool(line.for_female_family),
                    "item_name":     line.item_name,
                    "description":   line.description or "",
                    "group_name":    line.group_name or "",
                    "subgroup_name": line.subgroup_name or "",
                    "price_type":    line.price_type or "standard",
                    "note":          line.note or "",
                    "list_price":    int(line.list_price or 0),
                })
            # Ensure columns is always a list (in case columns_json is None or malformed)
            pkg_columns = pkg.columns_json
            if not isinstance(pkg_columns, list):
                pkg_columns = DEFAULT_PACKAGE_COLUMNS

            existing_packages.append({
                "db_id":   pkg.id,
                "name":    pkg.name,
                "columns": pkg_columns,
                "lines":   pkg_lines,
            })
    else:
        # Legacy: wrap existing lines in 1 default package
        legacy_lines = []
        for line in quotation.lines.order_by("display_order"):
            legacy_lines.append({
                "catalog_id":    line.catalog_id,
                "checked_male":  bool(line.checked_male),
                "checked_fs":    bool(line.checked_female_single),
                "checked_ff":    bool(line.checked_female_family),
                "price_male":    int(line.price_male or 0),
                "price_fs":      int(line.price_female_single or 0),
                "price_ff":      int(line.price_female_family or 0),
                "udai_male":     int(line.udai_price_male or 0),
                "udai_fs":       int(line.udai_price_fs or 0),
                "udai_ff":       int(line.udai_price_ff or 0),
                "pct_male":      float(line.discount_male_pct or 0),
                "pct_fs":        float(line.discount_fs_pct or 0),
                "pct_ff":        float(line.discount_ff_pct or 0),
                "extra_prices":  {},
                "for_m":         bool(line.for_male),
                "for_fs":        bool(line.for_female_single),
                "for_ff":        bool(line.for_female_family),
                "item_name":     line.item_name,
                "description":   line.description or "",
                "group_name":    line.group_name or "",
                "subgroup_name": line.subgroup_name or "",
                "price_type":    line.price_type or "standard",
                "note":          line.note or "",
                "list_price":    int(line.list_price or 0),
            })
        legacy_cols = [
            {"key": "male",          "label": "NAM",         "count": quotation.male_count or 0,          "discount_pct": float(quotation.discount_male_pct or 0)},
            {"key": "female_single", "label": "NỮ ĐỘC THÂN", "count": quotation.female_single_count or 0, "discount_pct": float(quotation.discount_fs_pct or 0)},
            {"key": "female_family", "label": "NỮ GIA ĐÌNH", "count": quotation.female_family_count or 0, "discount_pct": float(quotation.discount_ff_pct or 0)},
        ]
        existing_packages = [{
            "db_id":   None,
            "name":    "Gói khám",
            "columns": legacy_cols,
            "lines":   legacy_lines,
        }]

    package_templates_json = "[]"
    try:
        from pathlib import Path
        from django.conf import settings
        pt_path = Path(settings.BASE_DIR) / "apps" / "contract" / "static" / "contract" / "data" / "package_templates.json"
        if pt_path.exists():
            package_templates_json = pt_path.read_text(encoding="utf-8")
    except Exception:
        pass

    try:
        package_templates = json.loads(package_templates_json) if package_templates_json else []
    except (json.JSONDecodeError, TypeError):
        package_templates = []

    return render(request, "contract/staff/edit_quotation.html", {
        "quotation":               quotation,
        "groups":                  groups,
        "catalog_data":            catalog,
        "existing_packages":       existing_packages,
        "package_templates":       package_templates,
        "default_columns":         DEFAULT_PACKAGE_COLUMNS,
        "commission_sale_pct":     float(quotation.commission_sale_pct or 0),
        "commission_co_pct":       float(quotation.commission_co_pct or 0),
        "commission_sale_amount":  int(quotation.commission_sale_amount or 0),
        "commission_co_amount":    int(quotation.commission_co_amount or 0),
        "extra_content_value":     quotation.extra_content or "",
    })


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

    quotation_id = post.get("quotation_id") or ""
    snapshot_map = {}
    is_edit      = bool(quotation_id.strip())

    if is_edit:
        quotation = get_quotation_for_user_or_404(request.user, quotation_id.strip())
        quotation = decorate_quotation_contract_state(quotation)
        if quotation.is_locked:
            messages.error(request, "Báo giá này đã bị khóa.")
            return redirect("contract:quotation_preview", quotation_id=quotation.id)
        if quotation.has_contract:
            messages.error(request, "Báo giá này đã phát sinh hợp đồng nên không thể sửa.")
            return redirect("contract:quotation_preview", quotation_id=quotation.id)
        # Snapshot existing lines trước khi xóa
        for line in quotation.lines.all():
            if line.catalog_id is not None:
                snapshot_map[int(line.catalog_id)] = line
        quotation.lines.all().delete()
        quotation.packages.all().delete()
        # Khi sửa: reset về DRAFT nếu đang ở SUBMITTED/REJECTED
        if quotation.status not in (QuotationStatus.DRAFT, QuotationStatus.APPROVED):
            quotation.status = QuotationStatus.DRAFT
    else:
        quotation = QuotationDraft()

    # ── Thông tin cơ bản ─────────────────────────────────────────────────────
    company_address = (post.get("company_address") or "").strip()
    company = upsert_company_from_quotation(
        actor=request.user,
        name=company_name,
        address=company_address,
        company=quotation.company if quotation.pk else None,
    )

    quotation.created_by      = quotation.created_by if is_edit else request.user
    quotation.company         = company
    quotation.company_name    = company.name
    quotation.company_address = company.address or ""
    quotation.contact_name    = (post.get("contact_name") or "").strip()
    quotation.contact_phone   = (post.get("contact_phone") or "").strip()
    quotation.tax_code        = (post.get("tax_code") or "").strip()
    quotation.note            = (post.get("note") or "").strip()
    quotation.extra_content   = (post.get("extra_content") or "").strip()

    try:
        quotation.valid_until = date.fromisoformat(post.get("valid_until") or "")
    except (ValueError, TypeError):
        quotation.valid_until = date.today() + timedelta(days=30)

    quotation.pax_from = safe_int(post.get("pax_from"), 0) or None

    quotation.commission_sale_pct    = safe_decimal(post.get("commission_sale_pct"))
    quotation.commission_sale_amount = safe_decimal(post.get("commission_sale_amount"))
    quotation.commission_co_pct      = safe_decimal(post.get("commission_co_pct"))
    quotation.commission_co_amount   = safe_decimal(post.get("commission_co_amount"))

    # Legacy fields — backward compat
    quotation.male_count          = 0
    quotation.female_single_count = 0
    quotation.female_family_count = 0
    quotation.discount_male_pct   = Decimal("0")
    quotation.discount_fs_pct     = Decimal("0")
    quotation.discount_ff_pct     = Decimal("0")
    quotation.save()

    # ── Catalog map ───────────────────────────────────────────────────────────
    catalog     = load_catalog()
    catalog_map = {
        str(item["id"]): item
        for item in catalog
        if isinstance(item, dict) and "id" in item
    }

    # ── Xử lý gói khám ───────────────────────────────────────────────────────
    pkg_count = safe_int(post.get("pkg_count"), 0)
    if pkg_count == 0:
        quotation.delete()
        messages.error(request, "Chưa có gói khám nào. Vui lòng thêm ít nhất 1 gói.")
        return redirect("contract:create_proposal")

    has_any_line = False

    for pi in range(pkg_count):
        prefix   = f"pkg_{pi}_"
        pkg_name = (post.get(f"{prefix}name") or f"Gói khám {pi + 1}").strip()

        columns_raw = post.get(f"{prefix}columns_json") or ""
        try:
            columns_json = json.loads(columns_raw) if columns_raw else []
        except (json.JSONDecodeError, TypeError):
            columns_json = []
        if not columns_json:
            columns_json = list(DEFAULT_PACKAGE_COLUMNS)

        valid_columns = []
        for col in columns_json:
            if isinstance(col, dict) and "key" in col and "label" in col:
                valid_columns.append({
                    "key":          str(col["key"])[:30],
                    "label":        str(col.get("label", ""))[:50],
                    "count":        max(0, int(col.get("count") or 0)),
                    "discount_pct": max(0, min(100, float(col.get("discount_pct") or 0))),
                })
        if not valid_columns:
            valid_columns = list(DEFAULT_PACKAGE_COLUMNS)

        pkg_obj = QuotationPackage.objects.create(
            quotation=quotation,
            name=pkg_name,
            display_order=pi,
            columns_json=valid_columns,
        )

        selected_ids_raw = post.get(f"{prefix}selected_ids") or "[]"
        try:
            selected_ids = json.loads(selected_ids_raw)
        except (json.JSONDecodeError, TypeError):
            selected_ids = []

        lines = []
        for order, cid in enumerate(selected_ids):
            try:
                cid_int = int(cid)
            except (ValueError, TypeError):
                continue

            snap = snapshot_map.get(cid_int)
            cat  = catalog_map.get(str(cid_int))
            if snap is None and cat is None:
                continue

            checked_male = f"{prefix}checked_male_{cid}" in post
            checked_fs   = f"{prefix}checked_fs_{cid}"   in post
            checked_ff   = f"{prefix}checked_ff_{cid}"   in post

            if not (checked_male or checked_fs or checked_ff):
                extra_raw = post.get(f"{prefix}extra_{cid}") or "{}"
                try:
                    extra_prices_check = json.loads(extra_raw)
                except Exception:
                    extra_prices_check = {}
                if not extra_prices_check:
                    continue

            item_name     = (snap.item_name     if snap else None) or (cat.get("name", "")        if cat else "")
            description   = (snap.description   if snap else None) or (cat.get("description", "") if cat else "")
            group_name    = (snap.group_name    if snap else None) or (cat.get("group", "")       if cat else "")
            subgroup_name = (snap.subgroup_name if snap else None) or ((cat.get("subgroup") or "") if cat else "")
            list_price_v  = snap.list_price if snap else safe_decimal(cat.get("list_price") if cat else None)

            posted_price_type = (post.get(f"{prefix}price_type_{cid}") or "").strip().lower()
            if posted_price_type not in {"standard", "free", "gift"}:
                posted_price_type = ""

            posted_note = (post.get(f"{prefix}note_{cid}") or "").strip()

            price_type_v = (
                posted_price_type
                or (snap.price_type if snap else None)
                or (cat.get("price_type", "standard") if cat else "standard")
                or "standard"
            )

            note_v = posted_note
            if not note_v:
                note_v = (
                    (snap.note if snap else None)
                    or ((cat.get("note") or "") if cat else "")
                    or ("Miễn phí" if price_type_v == "free" else "Khuyến mãi" if price_type_v == "gift" else "")
                )

            if price_type_v == "free" and not note_v:
                note_v = "Miễn phí"
            elif price_type_v == "gift" and not note_v:
                note_v = "Khuyến mãi"

            for_m  = snap.for_male          if snap else (cat.get("for_male",  True)  if cat else True)
            for_fs = snap.for_female_single if snap else (cat.get("for_female_single", True) if cat else True)
            for_ff = snap.for_female_family if snap else (cat.get("for_female_family", True) if cat else True)

            # Closure: bind cid per iteration via default arg
            def _get_price(key, _prefix=prefix, _cid=cid, _cat=cat):
                raw = post.get(f"{_prefix}price_{key}_{_cid}")
                val = safe_decimal(raw)
                if val is None and _cat:
                    val = safe_decimal(_cat.get(f"price_{key}"))
                return val

            extra_raw = post.get(f"{prefix}extra_{cid}") or "{}"
            try:
                extra_prices = json.loads(extra_raw)
                extra_prices = {
                    k: int(v) for k, v in extra_prices.items()
                    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit())
                }
            except Exception:
                extra_prices = {}

            line = QuotationLine(
                quotation=quotation,
                package=pkg_obj,
                catalog_id=cid_int,
                item_name=item_name,
                description=description,
                group_name=group_name,
                subgroup_name=subgroup_name,
                list_price=list_price_v,
                price_type=price_type_v,
                note=note_v,
                for_male=for_m,
                for_female_single=for_fs,
                for_female_family=for_ff,
                udai_price_male=safe_decimal(post.get(f"{prefix}udai_male_{cid}")) if checked_male else None,
                udai_price_fs=safe_decimal(post.get(f"{prefix}udai_fs_{cid}"))     if checked_fs   else None,
                udai_price_ff=safe_decimal(post.get(f"{prefix}udai_ff_{cid}"))     if checked_ff   else None,
                discount_male_pct=safe_decimal(post.get(f"{prefix}pct_male_{cid}")) or Decimal("0"),
                discount_fs_pct=safe_decimal(post.get(f"{prefix}pct_fs_{cid}"))     or Decimal("0"),
                discount_ff_pct=safe_decimal(post.get(f"{prefix}pct_ff_{cid}"))     or Decimal("0"),
                price_male=_get_price("male")          if checked_male else None,
                price_female_single=_get_price("female_single") if checked_fs else None,
                price_female_family=_get_price("female_family") if checked_ff else None,
                checked_male=checked_male,
                checked_female_single=checked_fs,
                checked_female_family=checked_ff,
                extra_prices_json=extra_prices,
                display_order=order,
            )
            lines.append(line)
            has_any_line = True

        if lines:
            QuotationLine.objects.bulk_create(lines)

    if not has_any_line:
        quotation.delete()
        messages.error(request, "Chưa chọn dịch vụ nào cho bất kỳ gói nào.")
        return redirect("contract:create_proposal")

    messages.success(request, "Đã lưu báo giá thành công.")
    return redirect("contract:quotation_preview", quotation_id=quotation.pk)


# ── preview ──────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def quotation_preview(request, quotation_id):
    quotation = get_quotation_for_user_or_404(request.user, quotation_id)
    quotation = decorate_quotation_contract_state(quotation)

    context = build_quotation_preview_context(quotation)
    context["quotation"]          = quotation
    context["latest_issued"]      = get_latest_issued_quotation_document(quotation)
    context["linked_contract"]    = quotation.linked_contract
    context["can_edit_quotation"] = (not quotation.is_locked) and (not quotation.has_contract)
    context["can_issue_document"] = (not quotation.is_locked) and (not quotation_issue_blocked_by_contract(quotation))

    from apps.approvals.models import ApprovalRequest, ApprovalStatus
    from apps.approvals.policies import ApprovalPolicy
    pending_ar = ApprovalRequest.objects.filter(quotation=quotation, status=ApprovalStatus.PENDING).first()
    context["pending_ar"]    = pending_ar
    context["can_submit"]    = (
        quotation.status == QuotationStatus.DRAFT
        and not quotation.is_locked
        and not quotation.has_contract
    )
    context["doc_type"] = "QUOTATION"
    context["doc_id"]   = quotation.pk
    context["can_direct_approve"] = bool(pending_ar and ApprovalPolicy.can_approve(request.user, pending_ar))
    context["issue_error_modal"] = request.session.pop("quotation_issue_error_modal", None)
    return render(request, "contract/staff/quotation_preview.html", context)


# ── issue docx/pdf ───────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def issue_quotation_document_view(request, quotation_id):
    quotation = get_quotation_for_user_or_404(request.user, quotation_id)
    quotation = decorate_quotation_contract_state(quotation)

    if quotation.is_locked:
        messages.error(request, "Báo giá đã bị khóa, không thể phát hành lại tài liệu.")
        return redirect("contract:quotation_preview", quotation_id=quotation.pk)

    if quotation_issue_blocked_by_contract(quotation):
        messages.error(
            request,
            "Hợp đồng liên kết đã được duyệt hoặc đã bị khóa, không thể phát hành PDF báo giá."
        )
        return redirect("contract:quotation_preview", quotation_id=quotation.pk)

    try:
        issued = issue_quotation_document_strict(quotation=quotation, actor=request.user)
    except PdfConversionTimeoutError as exc:
        request.session["quotation_issue_error_modal"] = {
            "title": "Phat hanh PDF bi timeout",
            "body": str(exc),
        }
        messages.error(request, f"Khong the phat hanh tai lieu: {exc}")
        return redirect("contract:quotation_preview", quotation_id=quotation.pk)
    except PdfConversionError as exc:
        request.session["quotation_issue_error_modal"] = {
            "title": "Khong the phat hanh PDF",
            "body": str(exc),
        }
        messages.error(request, f"Khong the phat hanh tai lieu: {exc}")
        return redirect("contract:quotation_preview", quotation_id=quotation.pk)
    except Exception as exc:
        request.session["quotation_issue_error_modal"] = {
            "title": "Loi phat hanh tai lieu",
            "body": str(exc),
        }
        messages.error(request, f"Không thể phát hành tài liệu: {exc}")
        return redirect("contract:quotation_preview", quotation_id=quotation.pk)

    if issued.pdf_file:
        messages.success(request, "Đã phát hành báo giá PDF thành công.")
    else:
        messages.warning(request, "Đã lưu docx nhưng chưa tạo được PDF. Kiểm tra LibreOffice hoặc WeasyPrint.")

    return redirect("contract:quotation_preview", quotation_id=quotation.pk)


@login_required(login_url="authentication:staff_login")
def download_issued_quotation_docx(request, issued_id):
    issued = get_object_or_404(IssuedDocument, pk=issued_id, doc_type=IssuedDocument.DOC_TYPE_QUOTATION)
    return file_response(issued.docx_file)


@login_required(login_url="authentication:staff_login")
def download_issued_quotation_pdf(request, issued_id):
    issued = get_object_or_404(IssuedDocument, pk=issued_id, doc_type=IssuedDocument.DOC_TYPE_QUOTATION)
    return file_response(issued.pdf_file)


@login_required(login_url="authentication:staff_login")
def quotation_pdf(request):
    """
    GET view: render PDF trực tiếp từ báo giá mới nhất.
    Ưu tiên trả file đã issued; nếu chưa có → render HTML → WeasyPrint on-the-fly.
    """
    quotation_id  = request.GET.get("id")
    quotation     = get_quotation_for_user_or_404(request.user, quotation_id)
    latest_issued = get_latest_issued_quotation_document(quotation)
    if latest_issued and latest_issued.pdf_file:
        return file_response(latest_issued.pdf_file)

    # On-the-fly render
    context = build_quotation_preview_context(quotation)
    context["quotation"] = quotation
    context["today"]     = date.today()
    html_string = render_to_string("contract/staff/quotation_pdf.html", context, request=request)

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
    except (ImportError, OSError):
        return HttpResponse(html_string, content_type="text/html; charset=utf-8")


# ── delete ───────────────────────────────────────────────────────────────────

@login_required(login_url="authentication:staff_login")
def delete_quotation(request, pk):
    quotation = get_quotation_for_user_or_404(request.user, pk)
    quotation = decorate_quotation_contract_state(quotation)
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
    return render(request, "contract/staff/quotation_confirm_delete.html", {"quotation": quotation})
