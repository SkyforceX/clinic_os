"""
Service ký biên bản họp điện tử + push notification khi hoàn tất.
"""
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.meeting.domain.enums import MeetingStatus, ParticipantRole
from apps.meeting.domain.exceptions import (
    MeetingPermissionDenied,
    MeetingStateError,
    MeetingValidationError,
)
from apps.meeting.models import MeetingSession, MeetingSignature
from apps.meeting.policies import MeetingPolicy


@dataclass(frozen=True)
class SignMinutesCommand:
    session_id: int
    actor: object
    ip_address: str = ""
    user_agent:  str = ""
    department:  str = ""
    role_label:  str = ""


@transaction.atomic
def sign_meeting_minutes(cmd: SignMinutesCommand) -> MeetingSignature:
    session = (
        MeetingSession.objects
        .select_for_update()
        .prefetch_related("participants", "commitments", "dept_assignments", "signatures")
        .get(pk=cmd.session_id)
    )

    if not MeetingPolicy.can_sign_minutes(cmd.actor, session):
        raise MeetingPermissionDenied("Bạn không có quyền ký biên bản buổi họp này.")

    if session.status not in (MeetingStatus.CLOSED, MeetingStatus.SIGNED):
        raise MeetingStateError("Chỉ được ký khi buổi họp đã ở trạng thái CLOSED hoặc SIGNED.")

    if session.signatures.filter(user=cmd.actor).exists():
        raise MeetingValidationError("Bạn đã ký biên bản này rồi.")

    doc_hash = MeetingSignature.compute_hash(session)

    department = cmd.department
    if not department:
        p = session.participants.filter(user=cmd.actor).first()
        if p:
            department = p.department

    signature = MeetingSignature.objects.create(
        session    = session,
        user       = cmd.actor,
        department = department,
        role_label = str(cmd.role_label or "").strip(),
        doc_hash   = doc_hash,
        ip_address = cmd.ip_address or None,
        user_agent = str(cmd.user_agent or "").strip(),
    )

    _maybe_finalize_session(session)
    return signature


def _maybe_finalize_session(session: MeetingSession) -> None:
    lead_user_ids  = set(
        session.participants.filter(role=ParticipantRole.LEAD).values_list("user_id", flat=True)
    )
    signed_user_ids = set(session.signatures.values_list("user_id", flat=True))

    if lead_user_ids and lead_user_ids.issubset(signed_user_ids):
        MeetingSession.objects.filter(pk=session.pk).update(
            status=MeetingStatus.SIGNED,
            updated_at=timezone.now(),
        )
        _push_signed_notification(session)


def _push_signed_notification(session: MeetingSession) -> None:
    """Gửi thông báo in-app cho tất cả participant khi biên bản ký xong."""
    try:
        from apps.notifications.services.push import push
        participant_user_ids = list(
            session.participants.values_list("user_id", flat=True)
        )
        for uid in participant_user_ids:
            push(
                recipient_id=uid,
                event_type="reminder",
                title="Biên bản họp đã được ký",
                body=f'Biên bản buổi họp "{session.title}" ({session.meeting_date}) đã có đầy đủ chữ ký.',
                level="success",
                url=f"/meeting/{session.pk}/",
            )
    except Exception:
        pass  # không để lỗi notification block service chính


def verify_signature(*, signature: MeetingSignature) -> dict:
    session      = signature.session
    current_hash = MeetingSignature.compute_hash(session)
    is_valid     = current_hash == signature.doc_hash
    return {
        "is_valid":    is_valid,
        "signed_at":   signature.signed_at,
        "signer":      signature.user,
        "stored_hash": signature.doc_hash,
        "current_hash":current_hash,
        "tampered":    not is_valid,
    }
