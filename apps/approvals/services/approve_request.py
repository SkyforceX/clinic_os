"""
approve_request
───────────────
Phê duyệt một ApprovalRequest đang PENDING.
Tự động cập nhật trạng thái tài liệu gốc sau khi duyệt.
"""

from django.db import transaction
from django.utils import timezone

from apps.approvals.domain.exceptions import (
    ApprovalNotFound,
    ApprovalPermissionDenied,
    ApprovalStateError,
)
from apps.approvals.models import (
    ApprovalLog,
    ApprovalRequest,
    ApprovalRequestType,
    ApprovalStatus,
)
from apps.approvals.models.approval_log import ApprovalAction
from apps.approvals.policies import ApprovalPolicy


# ── Callbacks cập nhật document sau khi approve ──────────────────────────────

def _approve_quotation(ar: ApprovalRequest, actor):
    q = ar.quotation
    q.status    = "APPROVED"
    q.is_locked = True
    q.locked_at = timezone.now()
    q.locked_by = actor
    q.save(update_fields=["status", "is_locked", "locked_at", "locked_by", "updated_at"])


def _approve_contract(ar: ApprovalRequest, actor):
    from apps.contract.models.contract import ContractStatus
    c = ar.contract
    c.status      = ContractStatus.APPROVED
    c.approved_by = actor
    c.approved_at = timezone.now()
    c.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])


def _approve_payment_voucher(ar: ApprovalRequest, actor):
    v = ar.payment_voucher
    v.status = "APPROVED"
    v.save(update_fields=["status", "updated_at"])


def _approve_proposal(ar: ApprovalRequest, actor):
    p = ar.proposal
    p.status = "APPROVED"
    p.save(update_fields=["status", "updated_at"])


_CALLBACKS = {
    ApprovalRequestType.QUOTATION:       _approve_quotation,
    ApprovalRequestType.CONTRACT:        _approve_contract,
    ApprovalRequestType.PAYMENT_VOUCHER: _approve_payment_voucher,
    ApprovalRequestType.PROPOSAL:        _approve_proposal,
}


@transaction.atomic
def execute(*, approval_request_id: int, actor, reviewer_note: str = "") -> ApprovalRequest:
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

    if not ApprovalPolicy.can_approve(actor, ar):
        raise ApprovalPermissionDenied("Bạn không có quyền phê duyệt yêu cầu này.")

    if ar.status != ApprovalStatus.PENDING:
        raise ApprovalStateError(
            f"Yêu cầu không ở trạng thái Chờ duyệt "
            f"(hiện tại: {ar.get_status_display()})."
        )

    now = timezone.now()
    ar.status        = ApprovalStatus.APPROVED
    ar.reviewed_by   = actor
    ar.reviewed_at   = now
    ar.reviewer_note = reviewer_note
    ar.save(update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_note"])

    callback = _CALLBACKS.get(ar.request_type)
    if callback:
        callback(ar, actor)

    ApprovalLog.objects.create(
        approval_request=ar,
        actor=actor,
        action=ApprovalAction.APPROVED,
        note=reviewer_note,
    )

    # ── Thông báo realtime ────────────────────────────────────────────────────
    try:
        from django.urls import reverse
        from apps.notifications.models import EventType
        from apps.notifications.services.push import push

        if ar.requested_by:
            note_suffix = f"\nGhi chú: {reviewer_note}" if reviewer_note else ""
            push(
                recipients=ar.requested_by,
                event_type=EventType.APPROVAL_APPROVED,
                level="success",
                title=f"✅ Đã phê duyệt — {ar.get_request_type_display()}",
                body=(
                    f'"{ar.document_label}" vừa được '
                    f"{actor.get_full_name() or actor.username} phê duyệt.{note_suffix}"
                ),
                url=reverse("approvals:detail", args=[ar.pk]),
            )
    except Exception:
        pass

    return ar
