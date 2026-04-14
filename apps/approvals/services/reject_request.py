"""
reject_request
──────────────
Từ chối ApprovalRequest, trả document về DRAFT.
reviewer_note bắt buộc.
"""

from django.db import transaction
from django.utils import timezone

from apps.approvals.domain.exceptions import (
    ApprovalNotFound,
    ApprovalPermissionDenied,
    ApprovalStateError,
    ApprovalValidationError,
)
from apps.approvals.models import ApprovalLog, ApprovalRequest, ApprovalStatus
from apps.approvals.models.approval_log import ApprovalAction
from apps.approvals.policies import ApprovalPolicy


@transaction.atomic
def execute(*, approval_request_id: int, actor, reviewer_note: str) -> ApprovalRequest:
    if not reviewer_note or not reviewer_note.strip():
        raise ApprovalValidationError("Vui lòng nhập lý do từ chối.")

    # select_for_update() không được kết hợp select_related trên FK nullable
    # vì sinh outer join → PostgreSQL báo lỗi FOR UPDATE on outer join.
    # Dùng hai query riêng: lock trước, lazy-load document sau trong transaction.
    ar = (
        ApprovalRequest.objects
        .select_for_update(of=("self",))
        .filter(pk=approval_request_id)
        .first()
    )
    if ar is None:
        raise ApprovalNotFound("Không tìm thấy yêu cầu phê duyệt.")

    if not ApprovalPolicy.can_reject(actor, ar):
        raise ApprovalPermissionDenied("Bạn không có quyền từ chối yêu cầu này.")

    if ar.status != ApprovalStatus.PENDING:
        raise ApprovalStateError(
            f"Yêu cầu không ở trạng thái Chờ duyệt "
            f"(hiện tại: {ar.get_status_display()})."
        )

    ar.status        = ApprovalStatus.REJECTED
    ar.reviewed_by   = actor
    ar.reviewed_at   = timezone.now()
    ar.reviewer_note = reviewer_note.strip()
    ar.save(update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_note"])

    # Trả document về DRAFT để creator chỉnh sửa lại
    doc = ar.document
    if doc is not None:
        doc.status = "DRAFT"
        doc.save(update_fields=["status", "updated_at"])

    ApprovalLog.objects.create(
        approval_request=ar,
        actor=actor,
        action=ApprovalAction.REJECTED,
        note=reviewer_note.strip(),
    )

    # ── Thông báo realtime ────────────────────────────────────────────────────
    try:
        from django.urls import reverse
        from apps.notifications.models import EventType
        from apps.notifications.services.push import push

        if ar.requested_by:
            push(
                recipients=ar.requested_by,
                event_type=EventType.APPROVAL_REJECTED,
                level="danger",
                title=f"❌ Bị từ chối — {ar.get_request_type_display()}",
                body=(
                    f'"{ar.document_label}" bị từ chối bởi '
                    f"{actor.get_full_name() or actor.username}.\n"
                    f"Lý do: {reviewer_note.strip()}"
                ),
                url=reverse("approvals:detail", args=[ar.pk]),
            )
    except Exception:
        pass

    return ar
