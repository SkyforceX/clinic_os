"""
Service ký biên bản họp điện tử.

Luồng:
1. Tính SHA-256 hash của nội dung session tại thời điểm ký
2. Lưu MeetingSignature với hash + audit info
3. Nếu tất cả LEAD participant đã ký → chuyển session → SIGNED
4. (Optional) Render PDF biên bản và email cho tất cả participant

Không dùng PKI/CA bên ngoài — đủ giá trị pháp lý nội bộ
theo Nghị định 130/2018/NĐ-CP về chữ ký điện tử.
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
    user_agent: str = ""
    department: str = ""
    role_label: str = ""


@transaction.atomic
def sign_meeting_minutes(cmd: SignMinutesCommand) -> MeetingSignature:
    """
    Actor ký biên bản buổi họp.
    Session phải ở trạng thái CLOSED trước khi ký.
    """
    session = (
        MeetingSession.objects
        .select_for_update()
        .prefetch_related("participants", "commitments", "dept_assignments", "signatures")
        .get(pk=cmd.session_id)
    )

    if not MeetingPolicy.can_sign_minutes(cmd.actor, session):
        raise MeetingPermissionDenied("Bạn không có quyền ký biên bản buổi họp này.")

    if session.status not in (MeetingStatus.CLOSED, MeetingStatus.SIGNED):
        raise MeetingStateError(
            "Chỉ được ký khi buổi họp đã ở trạng thái CLOSED hoặc SIGNED."
        )

    if session.signatures.filter(user=cmd.actor).exists():
        raise MeetingValidationError("Bạn đã ký biên bản này rồi.")

    doc_hash = MeetingSignature.compute_hash(session)

    # Resolve department từ participant nếu không truyền
    department = cmd.department
    if not department:
        p = session.participants.filter(user=cmd.actor).first()
        if p:
            department = p.department

    signature = MeetingSignature.objects.create(
        session=session,
        user=cmd.actor,
        department=department,
        role_label=str(cmd.role_label or "").strip(),
        doc_hash=doc_hash,
        ip_address=cmd.ip_address or None,
        user_agent=str(cmd.user_agent or "").strip(),
    )

    # Kiểm tra đủ chữ ký LEAD → chuyển SIGNED
    _maybe_finalize_session(session)

    return signature


def _maybe_finalize_session(session: MeetingSession) -> None:
    """
    Nếu tất cả participant LEAD đã ký → chuyển session sang SIGNED.
    Được gọi sau mỗi lần ký.
    """
    lead_user_ids = set(
        session.participants
        .filter(role=ParticipantRole.LEAD)
        .values_list("user_id", flat=True)
    )
    signed_user_ids = set(
        session.signatures.values_list("user_id", flat=True)
    )

    if lead_user_ids and lead_user_ids.issubset(signed_user_ids):
        MeetingSession.objects.filter(pk=session.pk).update(
            status=MeetingStatus.SIGNED,
            updated_at=timezone.now(),
        )
        _send_signed_notification(session)


def _send_signed_notification(session: MeetingSession) -> None:
    """
    Hook để gửi email/notification khi biên bản đã ký đầy đủ.
    Implement sau khi có notification infrastructure.
    """
    # TODO: gửi email PDF biên bản cho tất cả participant
    pass


# ── Verify signature integrity ────────────────────────────────────────────────

def verify_signature(*, signature: MeetingSignature) -> dict:
    """
    Kiểm tra tính toàn vẹn của một chữ ký.
    So sánh hash được lưu với hash tính lại từ dữ liệu hiện tại.
    Nếu khác nhau → nội dung đã bị thay đổi sau khi ký.
    """
    session = signature.session
    current_hash = MeetingSignature.compute_hash(session)
    is_valid = current_hash == signature.doc_hash

    return {
        "is_valid": is_valid,
        "signed_at": signature.signed_at,
        "signer": signature.user,
        "stored_hash": signature.doc_hash,
        "current_hash": current_hash,
        "tampered": not is_valid,
    }
