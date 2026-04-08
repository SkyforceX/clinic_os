from django.db.models import Count, Q

from apps.meeting.domain.enums import MeetingStatus
from apps.meeting.models import DeptAssignment, MeetingSession
from apps.meeting.policies import MeetingPolicy


def list_sessions_for_user(user):
    """
    Danh sách buổi họp mà user có quyền xem.
    Manager thấy tất cả. User thường chỉ thấy sessions mình tạo
    hoặc đã được thêm vào danh sách participant.
    """
    qs = (
        MeetingSession.objects.select_related("contract", "company", "created_by")
        .prefetch_related("participants", "dept_assignments")
        .order_by("-meeting_date", "-created_at")
    )

    if MeetingPolicy.can_view_all_sessions(user):
        return qs

    return qs.filter(
        Q(created_by=user) | Q(participants__user=user)
    ).distinct()


def get_session_for_user(*, user, session_id: int):
    """
    Lấy một session cụ thể với full prefetch.
    Trả về None nếu không tồn tại hoặc user không có quyền.
    """
    qs = (
        MeetingSession.objects.select_related("contract", "company", "created_by", "closed_by")
        .prefetch_related(
            "participants__user",
            "dept_assignments__lead_user",
            "dept_assignments__staff_shifts__user",
            "commitments__assignee",
            "commitments__dept_assignment",
            "signatures__user",
        )
        .filter(pk=session_id)
    )

    session = qs.first()
    if session is None:
        return None

    if not MeetingPolicy.can_view_session(user, session):
        return None

    return session


def get_session_dashboard(*, session: MeetingSession) -> dict:
    """
    Tổng hợp tiến độ xác nhận của tất cả phòng ban.
    Dùng để render thanh trạng thái và cảnh báo trong UI.
    """
    assignments = list(
        session.dept_assignments.prefetch_related("staff_shifts").annotate(
            shift_count=Count("staff_shifts"),
            unconfirmed_shift_count=Count(
                "staff_shifts", filter=Q(staff_shifts__confirmed=False)
            ),
        )
    )

    total = len(assignments)
    confirmed = sum(1 for a in assignments if a.confirmed)

    return {
        "session": session,
        "total_depts": total,
        "confirmed_depts": confirmed,
        "unconfirmed_depts": total - confirmed,
        "progress_pct": int((confirmed / total * 100)) if total else 0,
        "step_label": session.step_label,
        "current_step": session.current_step,
        "assignments": assignments,
        "has_warnings": any(not a.confirmed for a in assignments),
        "is_ready_to_close": (
            confirmed == total
            and session.current_step >= 5
            and session.is_open
        ),
    }


def get_dept_summary(*, assignment: DeptAssignment) -> dict:
    """
    Metrics nhanh của một phòng ban: số nhân sự, ca sáng, ca chiều.
    """
    from apps.meeting.domain.enums import ShiftType

    shifts = list(assignment.staff_shifts.select_related("user").all())
    am_shifts = [s for s in shifts if s.shift in (ShiftType.AM, ShiftType.FULL)]
    pm_shifts = [s for s in shifts if s.shift in (ShiftType.PM, ShiftType.FULL)]

    return {
        "assignment": assignment,
        "dept_label": assignment.dept_label,
        "total_staff": len(shifts),
        "am_count": len(am_shifts),
        "pm_count": len(pm_shifts),
        "unconfirmed_count": sum(1 for s in shifts if not s.confirmed),
        "shifts": shifts,
    }
