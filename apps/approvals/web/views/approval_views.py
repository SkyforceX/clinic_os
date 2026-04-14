from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from apps.approvals.domain.exceptions import ApprovalDomainError, ApprovalPermissionDenied
from apps.approvals.models import ApprovalRequest, ApprovalRequestType, ApprovalStatus
from apps.approvals.models.approval_attachment import ApprovalAttachment
from apps.approvals.policies import ApprovalPolicy
from apps.approvals.selectors import (
    get_inbox_requests,
    get_my_requests,
    get_request_detail,
)
from apps.approvals.services import approve_request, recall_request, reject_request, revoke_approved_request
from apps.approvals.services import submit_for_approval

LOGIN_URL = "authentication:staff_login"


# ─────────────────────────────────────────────────────────────────────────────
# Inbox
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def inbox(request):
    if not ApprovalPolicy.can_view_inbox(request.user):
        raise Http404("Bạn không có quyền truy cập inbox phê duyệt.")

    status_filter = request.GET.get("status", "")
    type_filter   = request.GET.get("type", "")

    requests_qs = get_inbox_requests(
        status_filter=status_filter,
        type_filter=type_filter,
    )

    pending_count = requests_qs.filter(status=ApprovalStatus.PENDING).count() \
        if not status_filter else None

    return render(request, "approvals/staff/inbox.html", {
        "approval_requests": requests_qs,
        "status_filter":     status_filter,
        "type_filter":       type_filter,
        "status_choices":    ApprovalStatus.choices,
        "type_choices":      ApprovalRequestType.choices,
        "pending_count":     pending_count,
    })


# ─────────────────────────────────────────────────────────────────────────────
# My requests
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def my_requests(request):
    requests_qs = get_my_requests(request.user)
    return render(request, "approvals/staff/my_requests.html", {
        "approval_requests": requests_qs,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Detail
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def detail(request, pk: int):
    ar = get_request_detail(pk)
    if ar is None:
        raise Http404("Không tìm thấy yêu cầu phê duyệt.")
    if not ApprovalPolicy.can_view_request(request.user, ar):
        raise Http404("Bạn không có quyền xem yêu cầu này.")

    attachments = ar.attachments.select_related("uploaded_by").all()

    return render(request, "approvals/staff/detail.html", {
        "ar":          ar,
        "logs":        ar.logs.all(),
        "attachments": attachments,
        "can_approve": ApprovalPolicy.can_approve(request.user, ar),
        "can_reject":  ApprovalPolicy.can_reject(request.user, ar),
        "can_recall":  ApprovalPolicy.can_recall(request.user, ar),
        "can_revoke_approved": ApprovalPolicy.can_revoke_approved(request.user, ar),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Submit detail (trang nộp phê duyệt chi tiết)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def submit_detail(request, doc_type: str, doc_id: int):
    """
    Trang soạn và nộp yêu cầu phê duyệt đầy đủ:
    - Tiêu đề
    - Nội dung Quill rich text
    - Đính kèm nhiều tệp (lưu riêng tư)
    """
    # Tải document từ đúng model
    document = _load_document(doc_type, doc_id)
    if document is None:
        raise Http404("Không tìm thấy tài liệu.")

    if not ApprovalPolicy.can_submit(request.user, document):
        return HttpResponseForbidden()

    if document.status != "DRAFT":
        messages.warning(request, f"Tài liệu đang ở trạng thái «{document.status}», không thể nộp phê duyệt.")
        return redirect(_doc_redirect(doc_type, doc_id))

    if request.method == "POST":
        submission_title = (request.POST.get("submission_title") or "").strip()
        submission_body  = (request.POST.get("submission_body") or "").strip()
        requester_note   = (request.POST.get("requester_note") or "").strip()
        files            = request.FILES.getlist("attachments")

        if not submission_title:
            messages.error(request, "Vui lòng nhập tiêu đề trình duyệt.")
        else:
            try:
                ar = submit_for_approval.execute(
                    document=document,
                    actor=request.user,
                    requester_note=requester_note,
                    submission_title=submission_title,
                    submission_body=submission_body,
                    files=files or None,
                )
                messages.success(request, f"✅ Đã nộp phê duyệt thành công — yêu cầu #{ar.pk}.")
                return redirect("approvals:detail", pk=ar.pk)
            except (ApprovalDomainError, ApprovalPermissionDenied) as e:
                messages.error(request, str(e))

    type_label = dict(ApprovalRequestType.choices).get(doc_type.upper(), doc_type)

    return render(request, "approvals/staff/submit.html", {
        "document":    document,
        "doc_type":    doc_type,
        "doc_id":      doc_id,
        "type_label":  type_label,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Serve attachment (private file download/preview)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def serve_attachment(request, att_id: int):
    att = get_object_or_404(ApprovalAttachment.objects.select_related("approval_request"), pk=att_id)
    ar  = att.approval_request

    if not ApprovalPolicy.can_view_request(request.user, ar):
        return HttpResponseForbidden()

    as_attachment = request.GET.get("download") == "1"
    response = FileResponse(att.file.open("rb"), content_type=att.content_type or "application/octet-stream")
    if as_attachment:
        response["Content-Disposition"] = f'attachment; filename="{att.filename}"'
    else:
        response["Content-Disposition"] = f'inline; filename="{att.filename}"'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Approve / Reject / Recall (POST only)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
@require_POST
def approve(request, pk: int):
    try:
        ar = approve_request.execute(
            approval_request_id=pk,
            actor=request.user,
            reviewer_note=request.POST.get("reviewer_note", "").strip(),
        )
        messages.success(request, f"✅ Đã phê duyệt yêu cầu #{ar.pk}.")
    except ApprovalPermissionDenied as e:
        messages.error(request, str(e))
    except ApprovalDomainError as e:
        messages.error(request, str(e))

    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("approvals:inbox")


@login_required(login_url=LOGIN_URL)
@require_POST
def reject(request, pk: int):
    try:
        ar = reject_request.execute(
            approval_request_id=pk,
            actor=request.user,
            reviewer_note=request.POST.get("reviewer_note", "").strip(),
        )
        messages.warning(request, f"Đã từ chối yêu cầu #{ar.pk}.")
    except ApprovalPermissionDenied as e:
        messages.error(request, str(e))
    except ApprovalDomainError as e:
        messages.error(request, str(e))
    return redirect("approvals:detail", pk=pk)


@login_required(login_url=LOGIN_URL)
@require_POST
def recall(request, pk: int):
    try:
        ar = recall_request.execute(
            approval_request_id=pk,
            actor=request.user,
            note=request.POST.get("note", "").strip(),
        )
        messages.info(request, f"Đã thu hồi yêu cầu #{ar.pk}.")
    except ApprovalPermissionDenied as e:
        messages.error(request, str(e))
    except ApprovalDomainError as e:
        messages.error(request, str(e))
    return redirect("approvals:my_requests")


@login_required(login_url=LOGIN_URL)
@require_POST
def revoke_approved(request, pk: int):
    try:
        ar = revoke_approved_request.execute(
            approval_request_id=pk,
            actor=request.user,
            note=request.POST.get("note", "").strip(),
        )
        messages.warning(request, f"Da go phe duyet yeu cau #{ar.pk} va mo khoa tai lieu de chinh sua.")
    except ApprovalPermissionDenied as e:
        messages.error(request, str(e))
    except ApprovalDomainError as e:
        messages.error(request, str(e))
    return redirect("approvals:detail", pk=pk)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_document(doc_type: str, doc_id: int):
    try:
        from apps.contract.models import Contract, PaymentVoucher, ProposalForm, QuotationDraft
        mapping = {
            "QUOTATION":       QuotationDraft,
            "CONTRACT":        Contract,
            "PAYMENT_VOUCHER": PaymentVoucher,
            "PROPOSAL":        ProposalForm,
        }
        klass = mapping.get(doc_type.upper())
        if klass is None:
            return None
        return klass.objects.filter(pk=doc_id).first()
    except Exception:
        return None


def _doc_redirect(doc_type: str, doc_id: int) -> str:
    from django.urls import reverse
    try:
        if doc_type.upper() == "QUOTATION":
            return reverse("contract:quotation_preview", args=[doc_id])
        if doc_type.upper() == "CONTRACT":
            return reverse("contract:corporate_contract_detail", args=[doc_id])
    except Exception:
        pass
    return reverse("approvals:my_requests")
