from dataclasses import dataclass

from django.db import transaction

from apps.meeting.domain.enums import CommitmentStatus
from apps.meeting.domain.exceptions import (
    MeetingPermissionDenied,
    MeetingStateError,
    MeetingValidationError,
)
from apps.meeting.models import MeetingCommitment
from apps.meeting.policies import MeetingPolicy


@dataclass(frozen=True)
class AddCommitmentCommand:
    session_id: int
    actor: object
    title: str
    dept_assignment_id: int | None = None
    assignee_id: int | None = None
    deadline: object = None
    description: str = ""
    display_order: int = 0


@transaction.atomic
def add_commitment(cmd: AddCommitmentCommand) -> MeetingCommitment:
    from apps.meeting.models import DeptAssignment, MeetingSession

    session = MeetingSession.objects.select_related().get(pk=cmd.session_id)

    if not MeetingPolicy.can_edit_session(cmd.actor, session):
        raise MeetingPermissionDenied("Không có quyền chỉnh sửa buổi họp này.")

    if not session.is_open:
        raise MeetingStateError("Buổi họp đã đóng, không thể thêm cam kết.")

    title = str(cmd.title or "").strip()
    if not title:
        raise MeetingValidationError("Nội dung cam kết không được để trống.")

    # Resolve optional FKs
    dept_assignment = None
    if cmd.dept_assignment_id:
        try:
            dept_assignment = DeptAssignment.objects.get(
                pk=cmd.dept_assignment_id, session=session
            )
        except DeptAssignment.DoesNotExist:
            raise MeetingValidationError("Phòng ban không thuộc buổi họp này.")

    assignee = None
    if cmd.assignee_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            assignee = User.objects.get(pk=cmd.assignee_id)
        except User.DoesNotExist:
            raise MeetingValidationError("Người thực hiện không tồn tại.")

    deadline = None
    if cmd.deadline:
        from apps.contract.services.common import parse_date
        deadline = parse_date(cmd.deadline, required=False, field_label="deadline")

    # Tính display_order tự động nếu không truyền
    order = cmd.display_order
    if not order:
        last = session.commitments.order_by("-display_order").values_list(
            "display_order", flat=True
        ).first()
        order = (last or 0) + 10

    return MeetingCommitment.objects.create(
        session=session,
        dept_assignment=dept_assignment,
        title=title,
        description=str(cmd.description or "").strip(),
        assignee=assignee,
        deadline=deadline,
        status=CommitmentStatus.OPEN,
        display_order=order,
    )


@dataclass(frozen=True)
class UpdateCommitmentCommand:
    commitment_id: int
    actor: object
    title: str | None = None
    description: str | None = None
    assignee_id: int | None = None
    deadline: object = None
    status: str | None = None


@transaction.atomic
def update_commitment(cmd: UpdateCommitmentCommand) -> MeetingCommitment:
    commitment = (
        MeetingCommitment.objects
        .select_related("session")
        .select_for_update()
        .get(pk=cmd.commitment_id)
    )

    if not MeetingPolicy.can_edit_session(cmd.actor, commitment.session):
        raise MeetingPermissionDenied("Không có quyền chỉnh sửa cam kết này.")

    if cmd.title is not None:
        title = str(cmd.title).strip()
        if not title:
            raise MeetingValidationError("Nội dung cam kết không được để trống.")
        commitment.title = title

    if cmd.description is not None:
        commitment.description = str(cmd.description).strip()

    if cmd.assignee_id is not None:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            commitment.assignee = User.objects.get(pk=cmd.assignee_id)
        except User.DoesNotExist:
            raise MeetingValidationError("Người thực hiện không tồn tại.")

    if cmd.deadline is not None:
        from apps.contract.services.common import parse_date
        commitment.deadline = parse_date(cmd.deadline, required=False, field_label="deadline")

    if cmd.status is not None:
        valid = [s.value for s in CommitmentStatus]
        if cmd.status not in valid:
            raise MeetingValidationError(f"Trạng thái '{cmd.status}' không hợp lệ.")
        commitment.status = cmd.status

    commitment.save()
    return commitment


@dataclass(frozen=True)
class DeleteCommitmentCommand:
    commitment_id: int
    actor: object


@transaction.atomic
def delete_commitment(cmd: DeleteCommitmentCommand) -> None:
    commitment = (
        MeetingCommitment.objects
        .select_related("session")
        .get(pk=cmd.commitment_id)
    )

    if not MeetingPolicy.can_edit_session(cmd.actor, commitment.session):
        raise MeetingPermissionDenied("Không có quyền xóa cam kết này.")

    if not commitment.session.is_open:
        raise MeetingStateError("Buổi họp đã đóng, không thể xóa cam kết.")

    if commitment.has_task:
        raise MeetingStateError(
            "Cam kết này đã được tạo thành Task. "
            "Xóa Task tương ứng trước hoặc dùng update để hủy (CANCELLED)."
        )

    commitment.delete()
