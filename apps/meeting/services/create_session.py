from dataclasses import dataclass, field

from django.db import transaction

from apps.meeting.domain.enums import (
    DEPARTMENT_CHOICES,
    MeetingStatus,
    ParticipantRole,
)
from apps.meeting.domain.exceptions import (
    MeetingPermissionDenied,
    MeetingValidationError,
)
from apps.meeting.models import DeptAssignment, MeetingParticipant, MeetingSession
from apps.meeting.policies import MeetingPolicy


@dataclass(frozen=True)
class CreateSessionCommand:
    title: str
    meeting_date: object           # date hoặc str "YYYY-MM-DD"
    actor: object                  # request.user

    contract_id: int | None = None
    company_id: int | None = None
    meeting_time: object = None
    location: str = ""
    note: str = ""

    # Danh sách phòng ban sẽ tạo DeptAssignment
    department_codes: list = field(default_factory=list)

    # Danh sách participant ngoài actor (list of user_id)
    participant_user_ids: list = field(default_factory=list)


def _parse_date(value, *, label="ngày họp"):
    from apps.contract.services.common import parse_date  # reuse utility hiện có
    return parse_date(value, required=True, field_label=label)


def _validate(cmd: CreateSessionCommand) -> dict:
    if not cmd.title or not str(cmd.title).strip():
        raise MeetingValidationError("Tiêu đề buổi họp không được để trống.")

    meeting_date = _parse_date(cmd.meeting_date)

    valid_dept_codes = {code for code, _ in DEPARTMENT_CHOICES}
    invalid = [c for c in cmd.department_codes if c not in valid_dept_codes]
    if invalid:
        raise MeetingValidationError(f"Mã phòng ban không hợp lệ: {invalid}")

    return {
        "title": str(cmd.title).strip(),
        "meeting_date": meeting_date,
    }


@transaction.atomic
def execute(cmd: CreateSessionCommand) -> MeetingSession:
    if not MeetingPolicy.can_create_session(cmd.actor):
        raise MeetingPermissionDenied("Bạn không có quyền tạo buổi họp.")

    payload = _validate(cmd)

    # Resolve FK
    contract = None
    if cmd.contract_id:
        from apps.contract.models import Contract
        try:
            contract = Contract.objects.get(pk=cmd.contract_id)
        except Contract.DoesNotExist:
            raise MeetingValidationError("Hợp đồng không tồn tại.")

    company = None
    if cmd.company_id:
        from apps.organizations.models import Company
        try:
            company = Company.objects.get(pk=cmd.company_id)
        except Company.DoesNotExist:
            raise MeetingValidationError("Doanh nghiệp không tồn tại.")
    elif contract:
        company = contract.company

    session = MeetingSession.objects.create(
        title=payload["title"],
        meeting_date=payload["meeting_date"],
        meeting_time=cmd.meeting_time,
        location=str(cmd.location or "").strip(),
        note=str(cmd.note or "").strip(),
        contract=contract,
        company=company,
        status=MeetingStatus.OPEN,
        current_step=1,
        created_by=cmd.actor,
    )

    # Thêm actor là participant LEAD
    MeetingParticipant.objects.create(
        session=session,
        user=cmd.actor,
        role=ParticipantRole.LEAD,
        can_edit=True,
    )

    # Thêm participant list
    if cmd.participant_user_ids:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        users = User.objects.filter(pk__in=cmd.participant_user_ids)
        MeetingParticipant.objects.bulk_create(
            [
                MeetingParticipant(
                    session=session,
                    user=u,
                    role=ParticipantRole.MEMBER,
                    can_edit=True,
                )
                for u in users
                if u.pk != cmd.actor.pk
            ],
            ignore_conflicts=True,
        )

    # Tạo DeptAssignment cho từng phòng ban
    if cmd.department_codes:
        DeptAssignment.objects.bulk_create(
            [
                DeptAssignment(session=session, department=code)
                for code in cmd.department_codes
            ]
        )

    return session
