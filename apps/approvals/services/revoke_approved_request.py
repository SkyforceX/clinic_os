from django.db import transaction

from apps.approvals.domain.exceptions import (
    ApprovalNotFound,
    ApprovalPermissionDenied,
    ApprovalStateError,
    ApprovalValidationError,
)
from apps.approvals.models import ApprovalLog, ApprovalRequest, ApprovalRequestType, ApprovalStatus
from apps.approvals.models.approval_log import ApprovalAction
from apps.approvals.policies import ApprovalPolicy


def _revoke_quotation(ar: ApprovalRequest) -> None:
    quotation = ar.quotation
    if quotation is None:
        return

    quotation.status = "DRAFT"
    quotation.is_locked = False
    quotation.locked_at = None
    quotation.locked_by = None
    quotation.save(update_fields=["status", "is_locked", "locked_at", "locked_by", "updated_at"])


def _revoke_contract(ar: ApprovalRequest) -> None:
    contract = ar.contract
    if contract is None:
        return

    contract.status = "DRAFT"
    contract.is_locked = False
    contract.locked_at = None
    contract.locked_by = None
    contract.approved_by = None
    contract.approved_at = None
    contract.save(
        update_fields=[
            "status",
            "is_locked",
            "locked_at",
            "locked_by",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )


def _revoke_payment_voucher(ar: ApprovalRequest) -> None:
    voucher = ar.payment_voucher
    if voucher is None:
        return

    voucher.status = "DRAFT"
    voucher.save(update_fields=["status", "updated_at"])


def _revoke_proposal(ar: ApprovalRequest) -> None:
    proposal = ar.proposal
    if proposal is None:
        return

    proposal.status = "DRAFT"
    proposal.save(update_fields=["status", "updated_at"])


_CALLBACKS = {
    ApprovalRequestType.QUOTATION: _revoke_quotation,
    ApprovalRequestType.CONTRACT: _revoke_contract,
    ApprovalRequestType.PAYMENT_VOUCHER: _revoke_payment_voucher,
    ApprovalRequestType.PROPOSAL: _revoke_proposal,
}


@transaction.atomic
def execute(*, approval_request_id: int, actor, note: str) -> ApprovalRequest:
    if not note or not note.strip():
        raise ApprovalValidationError("Vui long nhap ly do go phe duyet.")

    ar = (
        ApprovalRequest.objects
        .select_for_update(of=("self",))
        .filter(pk=approval_request_id)
        .first()
    )
    if ar is None:
        raise ApprovalNotFound("Khong tim thay yeu cau phe duyet.")

    if not ApprovalPolicy.can_revoke_approved(actor, ar):
        raise ApprovalPermissionDenied("Ban khong co quyen go phe duyet yeu cau nay.")

    if ar.status != ApprovalStatus.APPROVED:
        raise ApprovalStateError(
            f"Yeu cau khong o trang thai Da duyet (hien tai: {ar.get_status_display()})."
        )

    callback = _CALLBACKS.get(ar.request_type)
    if callback:
        callback(ar)

    ar.status = ApprovalStatus.PENDING
    ar.reviewed_by = None
    ar.reviewed_at = None
    ar.reviewer_note = note.strip()
    ar.save(update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_note"])

    ApprovalLog.objects.create(
        approval_request=ar,
        actor=actor,
        action=ApprovalAction.RECALLED,
        note=f"Go phe duyet boi superadmin: {note.strip()}",
    )

    return ar
