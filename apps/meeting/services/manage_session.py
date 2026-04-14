from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.meeting.domain.enums import MEETING_STEP_MAX, MeetingStatus, ShiftType
from apps.meeting.domain.exceptions import (
    DeptAssignmentError,
    MeetingPermissionDenied,
    MeetingStateError,
    MeetingValidationError,
    StepAdvanceError,
)
from apps.meeting.models import DeptAssignment, MeetingSession, StaffShift
from apps.meeting.policies import MeetingPolicy


# ── Advance step ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AdvanceStepCommand:
    session_id: int
    actor: object


@transaction.atomic
def advance_step(cmd: AdvanceStepCommand) -> MeetingSession:
    session = MeetingSession.objects.select_for_update().get(pk=cmd.session_id)

    if not MeetingPolicy.can_advance_step(cmd.actor, session):
        raise MeetingPermissionDenied("Bạn không có quyền chuyển bước buổi họp.")

    if not session.is_open:
        raise MeetingStateError(f"Buổi họp đang ở trạng thái '{session.status}', không thể chuyển bước.")

    if session.current_step >= 2:
        unconfirmed = list(
            session.dept_assignments.filter(confirmed=False).values_list("department", flat=True)
        )
        if unconfirmed:
            raise StepAdvanceError(
                f"Còn {len(unconfirmed)} phòng ban chưa xác nhận: {unconfirmed}. "
                "Vui lòng hoàn tất trước khi chuyển bước."
            )

    if session.current_step >= MEETING_STEP_MAX:
        raise MeetingStateError(
            f"Đã ở bước cuối ({MEETING_STEP_MAX}). Sử dụng close_session() để đóng họp."
        )

    session.current_step += 1
    session.save(update_fields=["current_step", "updated_at"])
    return session


# ── Confirm / Unconfirm dept ──────────────────────────────────────────────────

@dataclass(frozen=True)
class ConfirmDeptCommand:
    assignment_id: int
    actor: object


@transaction.atomic
def confirm_dept_assignment(cmd: ConfirmDeptCommand) -> DeptAssignment:
    assignment = (
        DeptAssignment.objects.select_for_update()
        .select_related("session", "lead_user")
        .get(pk=cmd.assignment_id)
    )

    if not MeetingPolicy.can_confirm_dept(cmd.actor, assignment):
        raise MeetingPermissionDenied("Chỉ trưởng phòng hoặc manager mới có thể xác nhận phân công.")

    if not assignment.session.is_open:
        raise MeetingStateError("Buổi họp đã đóng, không thể xác nhận thêm.")

    if not assignment.staff_shifts.exists():
        raise DeptAssignmentError(
            f"Phòng '{assignment.dept_label}' chưa có nhân sự nào được phân công. "
            "Vui lòng thêm ít nhất một nhân viên trước khi xác nhận."
        )

    assignment.confirmed    = True
    assignment.confirmed_by = cmd.actor
    assignment.confirmed_at = timezone.now()
    assignment.save(update_fields=["confirmed", "confirmed_by", "confirmed_at", "updated_at"])
    return assignment


@dataclass(frozen=True)
class UnconfirmDeptCommand:
    assignment_id: int
    actor: object


@transaction.atomic
def unconfirm_dept_assignment(cmd: UnconfirmDeptCommand) -> DeptAssignment:
    assignment = (
        DeptAssignment.objects.select_for_update()
        .select_related("session")
        .get(pk=cmd.assignment_id)
    )

    if not MeetingPolicy.can_confirm_dept(cmd.actor, assignment):
        raise MeetingPermissionDenied("Không có quyền thay đổi xác nhận phòng ban này.")

    if not assignment.session.is_open:
        raise MeetingStateError("Buổi họp đã đóng.")

    assignment.confirmed    = False
    assignment.confirmed_by = None
    assignment.confirmed_at = None
    assignment.save(update_fields=["confirmed", "confirmed_by", "confirmed_at", "updated_at"])
    return assignment


# ── Add / Remove staff shift ──────────────────────────────────────────────────

@dataclass(frozen=True)
class AddStaffShiftCommand:
    assignment_id: int
    user_id: int
    actor: object
    role_in_day: str = ""
    shift: str = ShiftType.FULL
    time_from: object = None
    time_to: object = None
    note: str = ""


@transaction.atomic
def add_staff_shift(cmd: AddStaffShiftCommand) -> StaffShift:
    assignment = (
        DeptAssignment.objects.select_related("session").get(pk=cmd.assignment_id)
    )

    if not MeetingPolicy.can_edit_session(cmd.actor, assignment.session):
        raise MeetingPermissionDenied("Không có quyền chỉnh sửa buổi họp này.")

    if cmd.shift not in [s.value for s in ShiftType]:
        raise MeetingValidationError(f"Ca làm việc '{cmd.shift}' không hợp lệ.")

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(pk=cmd.user_id)
    except User.DoesNotExist:
        raise MeetingValidationError("Nhân viên không tồn tại.")

    shift, _ = StaffShift.objects.update_or_create(
        dept_assignment=assignment,
        user=user,
        defaults={
            "role_in_day": str(cmd.role_in_day or "").strip(),
            "shift":       cmd.shift,
            "time_from":   cmd.time_from,
            "time_to":     cmd.time_to,
            "note":        str(cmd.note or "").strip(),
            "confirmed":   True,
        },
    )

    # Auto-unconfirm assignment khi có thay đổi nhân sự
    if assignment.confirmed:
        assignment.confirmed    = False
        assignment.confirmed_by = None
        assignment.confirmed_at = None
        assignment.save(update_fields=["confirmed", "confirmed_by", "confirmed_at", "updated_at"])

    return shift


@dataclass(frozen=True)
class RemoveStaffShiftCommand:
    shift_id: int
    actor: object


@transaction.atomic
def remove_staff_shift(cmd: RemoveStaffShiftCommand) -> None:
    shift = (
        StaffShift.objects.select_related("dept_assignment__session").get(pk=cmd.shift_id)
    )

    if not MeetingPolicy.can_edit_session(cmd.actor, shift.dept_assignment.session):
        raise MeetingPermissionDenied("Không có quyền chỉnh sửa buổi họp này.")

    assignment = shift.dept_assignment
    shift.delete()

    if assignment.confirmed:
        assignment.confirmed    = False
        assignment.confirmed_by = None
        assignment.confirmed_at = None
        assignment.save(update_fields=["confirmed", "confirmed_by", "confirmed_at", "updated_at"])


# ── Close session ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CloseSessionCommand:
    session_id: int
    actor: object
    force: bool = False


@transaction.atomic
def close_session(cmd: CloseSessionCommand) -> MeetingSession:
    """
    Đóng buổi họp (OPEN → CLOSED).
    Tự động tạo tasks từ commitments + gửi notification.
    """
    session = MeetingSession.objects.select_for_update().get(pk=cmd.session_id)

    if not MeetingPolicy.can_close_session(cmd.actor, session):
        raise MeetingPermissionDenied("Không có quyền đóng buổi họp này.")

    if not session.is_open:
        raise MeetingStateError(f"Buổi họp đang ở trạng thái '{session.status}'.")

    if not cmd.force:
        unconfirmed = list(
            session.dept_assignments.filter(confirmed=False).values_list("department", flat=True)
        )
        if unconfirmed:
            raise StepAdvanceError(
                f"Còn {len(unconfirmed)} phòng ban chưa xác nhận. "
                "Dùng force=True (manager) để bỏ qua."
            )

    session.status       = MeetingStatus.CLOSED
    session.current_step = MEETING_STEP_MAX
    session.closed_by    = cmd.actor
    session.closed_at    = timezone.now()
    session.save(update_fields=["status", "current_step", "closed_by", "closed_at", "updated_at"])

    # Tạo tasks.Task từ commitments
    from apps.meeting.services.create_tasks import create_tasks_from_session
    created = create_tasks_from_session(session=session)

    # Gửi notification cho tất cả participant
    _push_close_notification(session, task_count=len(created))

    return session


def _push_close_notification(session: MeetingSession, task_count: int) -> None:
    """Push in-app notification khi session đóng và tasks được tạo."""
    try:
        from apps.notifications.services.push import push
        participant_ids = list(session.participants.values_list("user_id", flat=True))
        task_text = f" và tạo {task_count} công việc mới" if task_count else ""
        for uid in participant_ids:
            push(
                recipient_id=uid,
                event_type="reminder",
                title="Buổi họp đã kết thúc",
                body=f'Buổi họp "{session.title}" ({session.meeting_date}) đã đóng{task_text}.',
                level="info",
                url=f"/meeting/{session.pk}/",
            )
    except Exception:
        pass
