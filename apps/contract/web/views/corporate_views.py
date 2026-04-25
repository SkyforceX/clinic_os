from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F, OuterRef, Subquery
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.autoreload import logger
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.contract.models import Contract
from apps.contract.models.contract import CLOSED_STATUSES
from apps.contract.models.quotation import QuotationDraft, QuotationStatus
from apps.contract.policies import ContractPolicy
from apps.contract.services.corporate_contracts import (
    build_catalog_groups,
    build_quote_context,
    create_corporate_contract_from_request,
    get_corporate_contract_for_update,
    get_latest_quotation_for_company,
    unlock_corporate_contract, # chưa xóa để debug
    update_corporate_contract_from_request,
)
from apps.contract.services.contract_documents import (
        get_latest_issued_contract_document,
    )
from apps.contract.services.pdf_converter import PdfConversionError, PdfConversionTimeoutError
from apps.contract.services.strict_issue_documents import issue_contract_document_strict
from django.http import FileResponse, Http404
import mimetypes


def _normalize_form_error(exc):
    field_errors = {}
    message = "Dữ liệu không hợp lệ."

    if hasattr(exc, "message_dict"):
        for field, errors in exc.message_dict.items():
            field_errors[field] = [str(e) for e in errors]
        if field_errors:
            first_field = next(iter(field_errors))
            first_errors = field_errors[first_field]
            if first_errors:
                message = first_errors[0]
    elif hasattr(exc, "messages"):
        msgs = [str(e) for e in exc.messages]
        if msgs:
            message = msgs[0]
    else:
        message = str(exc)

    return {
        "message": message,
        "field_errors": field_errors,
    }


def _decorate_quotation_states(quotations):
    company_ids = {q.company_id for q in quotations if q.company_id}
    latest_ids_by_company = {}

    if company_ids:
        latest_company_quote_id = (
            QuotationDraft.objects
            .filter(
                company_id=OuterRef("company_id"),
                company__isnull=False,
                status=QuotationStatus.APPROVED,
            )
            .order_by("-created_at", "-id")
            .values("id")[:1]
        )

        latest_ids_by_company = {
            company_id: quotation_id
            for company_id, quotation_id in (
                QuotationDraft.objects
                .filter(
                    company_id__in=company_ids,
                    company__isnull=False,
                    status=QuotationStatus.APPROVED,
                )
                .annotate(latest_quote_id=Subquery(latest_company_quote_id))
                .filter(id=F("latest_quote_id"))
                .values_list("company_id", "id")
            )
        }

    for q in quotations:
        linked_profile = getattr(q, "corporate_contract_profile", None)
        linked_contract = getattr(linked_profile, "contract", None) if linked_profile else None
        q.linked_contract = linked_contract
        q.has_contract = linked_contract is not None
        q.is_latest_for_company = bool(
            q.company_id and latest_ids_by_company.get(q.company_id) == q.id
        )

        q.create_disabled_reason = ""
        if q.has_contract:
            q.create_disabled_reason = "Báo giá này đã phát sinh hợp đồng"
        elif not q.is_latest_for_company:
            q.create_disabled_reason = "Chỉ được tạo hợp đồng từ báo giá đã duyệt mới nhất"

    return quotations


@login_required(login_url="authentication:staff_login")
def create_corporate_contract(request):
    flag_nurse = ContractPolicy.is_nurse(request.user)
    catalog_groups = build_catalog_groups()
    
    quotations = list(
        QuotationDraft.objects
        .select_related("company", "created_by", "corporate_contract_profile__contract")
        .filter(
            company__isnull=False,
            status=QuotationStatus.APPROVED,
        )
        .order_by("-created_at")[:100]
    )
    quotations = _decorate_quotation_states(quotations)

    return render(
        request,
        "contract/staff/create_corporate_contract.html",
        {
            "flag_nurse": flag_nurse,
            "catalog_groups": catalog_groups,
            "quotations": quotations,
        },
    )


@login_required(login_url="authentication:staff_login")
@csrf_exempt
def save_corporate_contract(request):
    if request.method != "POST":
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "Phương thức không hợp lệ."},
                status=405,
            )
        return redirect("contract:corporate_contract_list")

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    try:
        contract = create_corporate_contract_from_request(request)

        if is_ajax:
            return JsonResponse(
                {
                    "ok": True,
                    "redirect_url": request.build_absolute_uri(
                        redirect("contract:corporate_contract_print", contract_id=contract.id).url
                    ),
                }
            )

        messages.success(request, "Đã tạo hợp đồng doanh nghiệp thành công ✅")
        return redirect("contract:corporate_contract_print", contract_id=contract.id)
    
    
    except ValidationError as exc:
        
        payload = _normalize_form_error(exc)
        
        if is_ajax:
            return JsonResponse(
                
                {
                    
                    "ok": False,
                    
                    "message": payload["message"],
                    
                    "field_errors": payload["field_errors"],
                    
                },
                
                status=400,
            
            )
        
        messages.error(request, f"Lỗi nhập liệu: {payload['message']}")

    except IntegrityError as exc:
        message = f"Lỗi dữ liệu: {exc}"
        if is_ajax:
            return JsonResponse({"ok": False, "message": message}, status=400)
        messages.error(request, message)

    except Exception as exc:
        message = f"Đã xảy ra lỗi: {exc}"
        if is_ajax:
            return JsonResponse({"ok": False, "message": message}, status=500)
        messages.error(request, message)

    return redirect("contract:create_corporate_contract")


@login_required(login_url="authentication:staff_login")
def edit_corporate_contract(request, contract_id):
    contract = get_object_or_404(
        Contract.objects.select_related(
            "company",
            "created_by",
            "corporate_profile",
            "corporate_profile__quotation",
        ),
        pk=contract_id,
        corporate_profile__isnull=False,
    )

    if not ContractPolicy.can_update(request.user, contract):
        if contract.is_locked:
            messages.error(request, "Hợp đồng đã chốt, không thể chỉnh sửa.")
        else:
            messages.error(request, "Bạn không có quyền sửa hợp đồng này.")
        return redirect("contract:corporate_contract_print", contract_id=contract.id)

    profile = contract.corporate_profile
    quotation = profile.quotation
    blood_collections = contract.blood_collection_schedules.order_by("collection_date", "id")
    flag_nurse = ContractPolicy.is_nurse(request.user)

    return render(
        request,
        "contract/staff/edit_corporate_contract.html",
        {
            "contract": contract,
            "profile": profile,
            "quotation": quotation,
            "blood_collections": blood_collections,
            "flag_nurse": flag_nurse,
        },
    )


@login_required(login_url="authentication:staff_login")
@csrf_exempt
def update_corporate_contract(request, contract_id):
    if request.method != "POST":
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Phương thức không hợp lệ."}, status=405)
        return redirect("contract:corporate_contract_print", contract_id=contract_id)

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    try:
        contract = update_corporate_contract_from_request(contract_id=contract_id, request=request)

        if is_ajax:
            return JsonResponse(
                {
                    "ok": True,
                    "redirect_url": request.build_absolute_uri(
                        redirect("contract:corporate_contract_print", contract_id=contract.id).url
                    ),
                }
            )

        messages.success(request, "Đã cập nhật hợp đồng doanh nghiệp ✅")
        return redirect("contract:corporate_contract_print", contract_id=contract.id)

    except ValidationError as exc:
        payload = _normalize_form_error(exc)
        if is_ajax:
            return JsonResponse(
                {
                    "ok": False,
                    "message": payload["message"],
                    "field_errors": payload["field_errors"],
                },
                status=400,
            )
        messages.error(request, payload["message"])

    except IntegrityError as exc:
        message = f"Lỗi dữ liệu: {exc}"
        if is_ajax:
            return JsonResponse({"ok": False, "message": message, "field_errors": {}}, status=400)
        messages.error(request, message)

    except Exception as exc:
        message = f"Đã xảy ra lỗi: {exc}"
        if is_ajax:
            return JsonResponse({"ok": False, "message": message, "field_errors": {}}, status=500)
        messages.error(request, message)

    return redirect("contract:edit_corporate_contract", contract_id=contract_id)


@login_required
@require_POST
@transaction.atomic
def delete_corporate_contract(request, pk):
    contract = get_object_or_404(
        Contract.objects.select_related("company", "corporate_profile", "corporate_profile__quotation"),
        pk=pk,
    )

    if contract.created_by_id != request.user.id:
        messages.error(request, "Bạn không có quyền xóa hợp đồng này.")
        return redirect("contract:corporate_contract_print", contract_id=contract.pk)

    if contract.is_locked or contract.is_approved:
        messages.error(request, "Không thể xóa hợp đồng đã chốt hoặc đã duyệt.")
        return redirect("contract:corporate_contract_print", contract_id=contract.pk)

    contract_number = contract.contract_number or f"#{contract.pk}"

    profile = getattr(contract, "corporate_profile", None)
    quotation = getattr(profile, "quotation", None) if profile else None

    # Mở khóa báo giá gốc trước khi xóa hợp đồng
    if quotation:
        quotation.is_locked = False
        quotation.locked_at = None
        quotation.locked_by = None
        quotation.save(update_fields=["is_locked", "locked_at", "locked_by", "updated_at"])

    # Gỡ liên kết quotation khỏi corporate profile trước khi xóa để trạng thái "đã phát sinh hợp đồng" mất ngay
    if profile and quotation:
        profile.quotation = None
        profile.save(update_fields=["quotation", "updated_at"])

    contract.delete()

    messages.success(request, f"Đã xóa hợp đồng {contract_number}. Báo giá gốc đã được mở lại.")
    return redirect("contract:corporate_contract_list")


@login_required(login_url="authentication:staff_login")
def corporate_contract_list(request):
    today = timezone.now().date()
    expired_date = today - timedelta(days=21)

    qs = Contract.objects.select_related(
        "company",
        "created_by",
        "corporate_profile",
        "corporate_profile__quotation",
    ).filter(corporate_profile__isnull=False)

    if ContractPolicy.is_manager(request.user):
        contracts = list(qs.order_by("-created_at"))
    else:
        contracts = list(
            qs.exclude(
                status__in=CLOSED_STATUSES,
            ).filter(
                created_at__date__gt=expired_date,
                created_by=request.user,
            ).order_by("-created_at")
        )

    # Gắn pending_ar cho mỗi hợp đồng — 1 query duy nhất
    from apps.approvals.models import ApprovalRequest, ApprovalStatus
    contract_ids = [c.pk for c in contracts]
    pending_map = {
        ar.contract_id: ar
        for ar in ApprovalRequest.objects.filter(
            contract_id__in=contract_ids,
            status=ApprovalStatus.PENDING,
        )
    }
    for c in contracts:
        c.pending_ar = pending_map.get(c.pk)

    return render(
        request,
        "contract/staff/corporate_contract_list.html",
        {
            "contracts": contracts,
            "is_manager": ContractPolicy.is_manager(request.user),
        },
    )

# xóa def này
@login_required(login_url="authentication:staff_login")
def corporate_quote_print(request, contract_id):
    contract = get_object_or_404(
        Contract.objects.select_related(
            "company",
            "corporate_profile",
            "corporate_profile__quotation",
            "created_by",
        ),
        pk=contract_id,
        corporate_profile__isnull=False,
    )

    if not (ContractPolicy.is_manager(request.user) or contract.created_by_id == request.user.id):
        messages.error(request, "Bạn không có quyền xem báo giá này.")
        return redirect("contract:corporate_contract_list")

    context = build_quote_context(contract)
    context["can_unlock_contract"] = request.user.is_superuser
    return render(request, "contract/staff/corporate_quote_print.html", context)


@login_required(login_url="authentication:staff_login")
def corporate_contract_print(request, contract_id):
    from apps.contract.services.contract_documents import get_latest_issued_contract_document
    
    contract = get_object_or_404(
        Contract.objects.select_related(
            "company",
            "corporate_profile",
            "corporate_profile__quotation",
            "created_by",
        ),
        pk=contract_id,
        corporate_profile__isnull=False,
    )
    
    if not (ContractPolicy.is_manager(request.user) or contract.created_by_id == request.user.id):
        messages.error(request, "Bạn không có quyền xem hợp đồng này.")
        return redirect("contract:corporate_contract_list")
    
    context = build_quote_context(contract)
    context["can_unlock_contract"] = request.user.is_superuser
    context["can_edit_contract"] = ContractPolicy.can_update(request.user, contract)
    context["can_delete_contract"] = (
        contract.created_by_id == request.user.id
        and not contract.is_locked
    )

    # ── truyền bản phát hành mới nhất để hiện nút tải ──────────────────
    context["latest_issued"] = get_latest_issued_contract_document(contract)

    # ── Approval context ────────────────────────────────────────────────
    from apps.approvals.models import ApprovalRequest, ApprovalStatus
    from apps.approvals.policies import ApprovalPolicy
    
    pending_ar = (
        ApprovalRequest.objects
        .filter(contract=contract, status=ApprovalStatus.PENDING)
        .first()
    )
    context["pending_ar"]   = pending_ar
    context["can_submit"]   = (
        contract.status == "DRAFT"
        and not contract.is_locked
    )
    context["doc_type"] = "CONTRACT"
    context["doc_id"]   = contract.pk
    context["can_direct_approve"] = bool(
        pending_ar and ApprovalPolicy.can_approve(request.user, pending_ar)
    )
    context["issue_error_modal"] = request.session.pop("contract_issue_error_modal", None)

    return render(request, "contract/staff/corporate_contract_preview.html", context)


@login_required(login_url="authentication:staff_login")
@require_POST
def lock_corporate_contract_view(request, contract_id):
    try:
        lock_corporate_contract(contract_id=contract_id, actor=request.user)
        messages.success(request, "Đã chốt hợp đồng và khóa báo giá liên kết.")
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect("contract:corporate_contract_print", contract_id=contract_id)


@login_required(login_url="authentication:staff_login")
@require_POST
def unlock_corporate_contract_view(request, contract_id):
    try:
        unlock_corporate_contract(contract_id=contract_id, actor=request.user)
        messages.success(request, "Đã gỡ chốt hợp đồng và mở khóa báo giá liên kết.")
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect("contract:corporate_contract_print", contract_id=contract_id)



# ─── corporate render ──────────────────────────


@login_required(login_url="authentication:staff_login")
@require_POST
def issue_contract_document_view(request, contract_id):
    """
    POST /corporate/<id>/issue/
    Phát hành hợp đồng → render docx + PDF → lưu IssuedDocument.
    Redirect về trang print với thông báo kết quả.
    """
    from apps.contract.services.contract_documents import issue_contract_document

    contract = get_object_or_404(
        Contract.objects.select_related(
            "corporate_profile",
            "corporate_profile__quotation",
            "company",
        ),
        pk=contract_id,
        corporate_profile__isnull=False,
    )

    # Chỉ manager hoặc người tạo mới được phát hành
    if not (
        ContractPolicy.is_manager(request.user)
        or contract.created_by_id == request.user.id
    ):
        messages.error(request, "Bạn không có quyền phát hành hợp đồng này.")
        return redirect("contract:corporate_contract_print", contract_id=contract_id)

    try:
        issued = issue_contract_document_strict(
            contract=contract,
            actor=request.user,
        )
    except PdfConversionTimeoutError as exc:
        request.session["contract_issue_error_modal"] = {
            "title": "Phat hanh PDF bi timeout",
            "body": str(exc),
        }
        logger.error("LibreOffice timeout khi phat hanh hop dong #%s: %s", contract_id, exc, exc_info=True)
        messages.error(request, f"Khong the phat hanh hop dong: {exc}")
        return redirect("contract:corporate_contract_print", contract_id=contract_id)
    except PdfConversionError as exc:
        request.session["contract_issue_error_modal"] = {
            "title": "Khong the phat hanh PDF",
            "body": str(exc),
        }
        logger.error("LibreOffice loi khi phat hanh hop dong #%s: %s", contract_id, exc, exc_info=True)
        messages.error(request, f"Khong the phat hanh hop dong: {exc}")
        return redirect("contract:corporate_contract_print", contract_id=contract_id)
    except Exception as exc:
        request.session["contract_issue_error_modal"] = {
            "title": "Loi phat hanh tai lieu",
            "body": str(exc),
        }
        logger.error("Loi phat hanh hop dong #%s: %s", contract_id, exc, exc_info=True)
        messages.error(request, f"Khong the phat hanh hop dong: {exc}")
        return redirect("contract:corporate_contract_print", contract_id=contract_id)

    messages.success(
        request,
        f"Da phat hanh hop dong PDF thanh cong (v{issued.version}).",
    )
    return redirect("contract:corporate_contract_print", contract_id=contract_id)

    try:
        issued = issue_contract_document(
            contract=contract,
            actor=request.user,
            request=request,
        )

        if issued.pdf_file:
            messages.success(
                request,
                f"✅ Đã phát hành hợp đồng PDF thành công (v{issued.version}).",
            )
        else:
            messages.warning(
                request,
                f"⚠️ Đã tạo file Word (v{issued.version}) nhưng chưa convert được PDF. "
                "Kiểm tra LibreOffice hoặc tải file .docx về.",
            )

    except Exception as exc:
        logger.error("Lỗi phát hành hợp đồng #%s: %s", contract_id, exc, exc_info=True)
        messages.error(request, f"Không thể phát hành hợp đồng: {exc}")

    return redirect("contract:corporate_contract_print", contract_id=contract_id)


@login_required(login_url="authentication:staff_login")
def download_issued_contract_docx(request, issued_id):
    """
    GET /corporate/issued/<issued_id>/docx/
    Tải file .docx của IssuedDocument hợp đồng.
    """
    from apps.contract.models.document import IssuedDocument
    from django.http import FileResponse, Http404

    issued = get_object_or_404(
        IssuedDocument,
        pk=issued_id,
        doc_type=IssuedDocument.DOC_TYPE_CONTRACT,
    )

    # Kiểm tra quyền: manager hoặc người tạo
    contract = issued.contract
    if contract:
        if not (
            ContractPolicy.is_manager(request.user)
            or contract.created_by_id == request.user.id
        ):
            raise Http404

    if not issued.docx_file:
        raise Http404("File .docx không tồn tại.")

    try:
        response = FileResponse(
            issued.docx_file.open("rb"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            filename=f"hop-dong-{contract.pk if contract else issued_id}-v{issued.version}.docx",
        )
        return response
    except FileNotFoundError:
        raise Http404("File không còn tồn tại trên server.")


@login_required(login_url="authentication:staff_login")
def download_issued_contract_pdf(request, issued_id):
    """
    GET /corporate/issued/<issued_id>/pdf/
    Tải file .pdf của IssuedDocument hợp đồng.
    """
    from apps.contract.models.document import IssuedDocument
    from django.http import FileResponse, Http404

    issued = get_object_or_404(
        IssuedDocument,
        pk=issued_id,
        doc_type=IssuedDocument.DOC_TYPE_CONTRACT,
    )

    contract = issued.contract
    if contract:
        if not (
            ContractPolicy.is_manager(request.user)
            or contract.created_by_id == request.user.id
        ):
            raise Http404

    if not issued.pdf_file:
        raise Http404("File PDF không tồn tại.")

    try:
        response = FileResponse(
            issued.pdf_file.open("rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=f"hop-dong-{contract.pk if contract else issued_id}-v{issued.version}.pdf",
        )
        return response
    except FileNotFoundError:
        raise Http404("File không còn tồn tại trên server.")
