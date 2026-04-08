from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.autoreload import logger
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.contract.models import Contract
from apps.contract.models.contract import CLOSED_STATUSES
from apps.contract.models.quotation import QuotationDraft
from apps.contract.policies import ContractPolicy
from apps.contract.services.corporate_contracts import (
    build_catalog_groups,
    build_quote_context,
    create_corporate_contract_from_request,
    get_corporate_contract_for_update,
    get_latest_quotation_for_company,
    lock_corporate_contract,
    unlock_corporate_contract,
    update_corporate_contract_from_request,
)
from apps.contract.services.contract_documents import (
        get_latest_issued_contract_document,
        issue_contract_document,
    )
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
    latest_ids_by_company = {
        q.company_id: q.id
        for q in (
            QuotationDraft.objects
            .filter(company__isnull=False)
            .order_by("company_id", "-created_at", "-id")
            .distinct("company_id")
        )
    }

    for q in quotations:
        linked_profile = getattr(q, "corporate_contract_profile", None)
        linked_contract = getattr(linked_profile, "contract", None) if linked_profile else None
        q.linked_contract = linked_contract
        q.has_contract = linked_contract is not None
        q.is_latest_for_company = bool(q.company_id and latest_ids_by_company.get(q.company_id) == q.id)

        q.create_disabled_reason = ""
        if q.has_contract:
            q.create_disabled_reason = "Báo giá này đã phát sinh hợp đồng"
        elif not q.is_latest_for_company:
            q.create_disabled_reason = "Chỉ được tạo hợp đồng từ báo giá mới nhất"

    return quotations


@login_required(login_url="authentication:staff_login")
def create_corporate_contract(request):
    flag_nurse = ContractPolicy.is_nurse(request.user)
    catalog_groups = build_catalog_groups()

    quotations = list(
        QuotationDraft.objects
        .select_related("company", "created_by", "corporate_contract_profile__contract")
        .filter(company__isnull=False)
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
        Contract.objects.select_related("company", "corporate_profile"),
        pk=pk,
    )

    if contract.created_by_id != request.user.id:
        messages.error(request, "Bạn không có quyền xóa hợp đồng này.")
        return redirect("contract:corporate_contract_print", pk=contract.pk)
    
    if contract.is_locked or contract.is_approved:
        messages.error(request, "Không thể xóa hợp đồng đã chốt hoặc đã duyệt.")
        return redirect("contract:corporate_contract_print", pk=contract.pk)

    contract_number = contract.contract_number or f"#{contract.pk}"
    contract.delete()

    messages.success(request, f"Đã xóa hợp đồng {contract_number}.")
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
        contracts = qs.order_by("-created_at")
    else:
        contracts = qs.exclude(
            status__in=CLOSED_STATUSES,
        ).filter(
            created_at__date__gt=expired_date,
            created_by=request.user,
        ).order_by("-created_at")
    
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
    context["can_lock_contract"] = (
        request.user.is_superuser
        or ContractPolicy.is_manager(request.user)
        or contract.created_by_id == request.user.id
    )
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
    context["can_lock_contract"] = (
        request.user.is_superuser
        or ContractPolicy.is_manager(request.user)
        or contract.created_by_id == request.user.id
    )
    context["can_unlock_contract"] = request.user.is_superuser
    context["can_edit_contract"] = ContractPolicy.can_update(request.user, contract)
    context["can_delete_contract"] = (
        contract.created_by_id == request.user.id
        and not contract.is_locked
    )
    
    # ── truyền bản phát hành mới nhất để hiện nút tải ──────────────────
    context["latest_issued"] = get_latest_issued_contract_document(contract)
    
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