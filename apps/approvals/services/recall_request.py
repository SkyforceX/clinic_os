"""
recall_request
──────────────
Người nộp thu hồi yêu cầu đang PENDING, document trả về DRAFT.
"""

from django.db import transaction

from apps.approvals.domain.exceptions import (
    ApprovalNotFound,
    ApprovalPermissionDenied,
    ApprovalStateError,
)
from apps.approvals.models import ApprovalLog, ApprovalRequest, ApprovalStatus
from apps.approvals.models.approval_log import ApprovalAction
from apps.approvals.policies import ApprovalPolicy


@transaction.atomic
def execute(*, approval_request_id: int, actor, note: str = "") -> ApprovalRequest:
    # select_for_update() + select_related trên FK nullable sinh outer join
    # → PostgreSQL không cho phép FOR UPDATE on outer join.
    ar = (
        ApprovalRequest.objects
        .select_for_update(of=("self",))
        .filter(pk=approval_request_id)
        .first()
    )
    if ar is None:
        raise ApprovalNotFound("Không tìm thấy yêu cầu phê duyệt.")

    if not ApprovalPolicy.can_recall(actor, ar):
        raise ApprovalPermissionDenied(
            "Bạn không có quyền thu hồi yêu cầu này."
        )

    if ar.status != ApprovalStatus.PENDING:
        raise ApprovalStateError(
            f"Chỉ thu hồi được khi đang Chờ duyệt "
            f"(hiện tại: {ar.get_status_display()})."
        )

    ar.status = ApprovalStatus.RECALLED
    ar.save(update_fields=["status"])

    doc = ar.document
    if doc is not None:
        doc.status = "DRAFT"
        doc.save(update_fields=["status", "updated_at"])

    ApprovalLog.objects.create(
        approval_request=ar,
        actor=actor,
        action=ApprovalAction.RECALLED,
        note=note.strip() if note else "",
    )

    # ── Thông báo realtime ────────────────────────────────────────────────────
    try:
        from django.urls import reverse
        from apps.notifications.models import EventType
        from apps.notifications.services.push import push_to_managers

        actor_name = actor.get_full_name() or actor.username
        push_to_managers(
            event_type=EventType.APPROVAL_RECALLED,
            level="warning",
            title=f"↩ Thu hồi yêu cầu — {ar.get_request_type_display()}",
            body=f"{actor_name} vừa thu hồi yêu cầu #{ar.pk}: \"{ar.document_label}\".",
            url=reverse("approvals:detail", args=[ar.pk]),
        )
    except Exception:
        pass

    return ar
