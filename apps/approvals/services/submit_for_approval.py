"""
submit_for_approval
───────────────────
Nộp một tài liệu vào hàng chờ phê duyệt.

Luồng:
  1. Validate document đang DRAFT
  2. Kiểm tra chưa có request PENDING đang mở
  3. Đổi document.status → SUBMITTED
  4. Tạo ApprovalRequest(status=PENDING) với submission_title + submission_body
  5. Lưu file đính kèm (ApprovalAttachment)
  6. Ghi ApprovalLog(SUBMITTED)
"""

from django.db import transaction

from apps.approvals.domain.exceptions import (
    ApprovalPermissionDenied,
    ApprovalValidationError,
)
from apps.approvals.models import (
    ApprovalLog,
    ApprovalRequest,
    ApprovalRequestType,
    ApprovalStatus,
)
from apps.approvals.models.approval_log import ApprovalAction
from apps.approvals.policies import ApprovalPolicy


def _classify_document(document):
    """Xác định (request_type, fk_field) từ loại object."""
    from apps.contract.models import Contract, PaymentVoucher, ProposalForm, QuotationDraft

    mapping = {
        QuotationDraft:  (ApprovalRequestType.QUOTATION,       "quotation"),
        Contract:        (ApprovalRequestType.CONTRACT,        "contract"),
        PaymentVoucher:  (ApprovalRequestType.PAYMENT_VOUCHER, "payment_voucher"),
        ProposalForm:    (ApprovalRequestType.PROPOSAL,        "proposal"),
    }
    for klass, result in mapping.items():
        if isinstance(document, klass):
            return result
    raise ApprovalValidationError(
        f"Loại tài liệu '{type(document).__name__}' không hỗ trợ phê duyệt."
    )


def _save_attachments(ar: ApprovalRequest, actor, files: list) -> None:
    from apps.approvals.models.approval_attachment import ApprovalAttachment
    for f in files:
        if not f or not getattr(f, "name", None):
            continue
        ApprovalAttachment.objects.create(
            approval_request=ar,
            uploaded_by=actor,
            file=f,
            filename=f.name,
            file_size=f.size,
            content_type=getattr(f, "content_type", ""),
        )


@transaction.atomic
def execute(
    *,
    document,
    actor,
    requester_note: str = "",
    submission_title: str = "",
    submission_body: str = "",
    files: list | None = None,
) -> ApprovalRequest:
    """
    document          -- QuotationDraft / Contract / PaymentVoucher / ProposalForm
    actor             -- request.user
    requester_note    -- ghi chú ngắn (backward compat)
    submission_title  -- tiêu đề chi tiết trình duyệt
    submission_body   -- nội dung HTML soạn bằng Quill
    files             -- list of UploadedFile (tệp đính kèm riêng tư)
    """
    if document is None:
        raise ApprovalValidationError("Không tìm thấy tài liệu.")

    if not ApprovalPolicy.can_submit(actor, document):
        raise ApprovalPermissionDenied("Bạn chưa đăng nhập.")

    request_type, fk_field = _classify_document(document)

    current_status = getattr(document, "status", None)
    if current_status != "DRAFT":
        label = current_status or "(không có status)"
        raise ApprovalValidationError(
            f"Tài liệu phải ở trạng thái Nháp mới được nộp phê duyệt "
            f"(hiện tại: {label})."
        )

    already_pending = ApprovalRequest.objects.filter(
        **{fk_field: document},
        status=ApprovalStatus.PENDING,
    ).exists()
    if already_pending:
        raise ApprovalValidationError(
            "Tài liệu này đang có yêu cầu phê duyệt chờ xử lý."
        )

    # Đổi trạng thái document
    document.status = "SUBMITTED"
    document.save(update_fields=["status", "updated_at"])

    # Tạo ApprovalRequest
    ar = ApprovalRequest.objects.create(
        request_type=request_type,
        status=ApprovalStatus.PENDING,
        **{fk_field: document},
        requested_by=actor,
        requester_note=requester_note,
        submission_title=submission_title.strip(),
        submission_body=submission_body.strip(),
    )

    # Lưu file đính kèm
    if files:
        _save_attachments(ar, actor, files)

    # Ghi audit log
    ApprovalLog.objects.create(
        approval_request=ar,
        actor=actor,
        action=ApprovalAction.SUBMITTED,
        note=requester_note or submission_title,
    )

    # ── Thông báo realtime ────────────────────────────────────────────────────
    try:
        from django.urls import reverse
        from apps.notifications.models import EventType
        from apps.notifications.services.push import push, push_to_managers

        url = reverse("approvals:detail", args=[ar.pk])
        actor_name = actor.get_full_name() or actor.username

        push_to_managers(
            event_type=EventType.APPROVAL_SUBMITTED,
            level="info",
            title=f"Yêu cầu phê duyệt mới — {ar.get_request_type_display()}",
            body=f"{actor_name} vừa nộp: {ar.document_label}",
            url=url,
            exclude_user=actor,
        )

        push(
            recipients=actor,
            event_type=EventType.APPROVAL_SUBMITTED,
            level="success",
            title="Đã nộp phê duyệt thành công",
            body=f'Yêu cầu #{ar.pk} cho "{ar.document_label}" đang chờ Managers xem xét.',
            url=url,
        )
    except Exception:
        pass

    return ar
