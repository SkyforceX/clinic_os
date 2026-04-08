from django.utils import timezone

from apps.meeting.domain.enums import CommitmentStatus
from apps.meeting.models import MeetingCommitment


def list_commitments_for_session(*, session_id: int):
    return (
        MeetingCommitment.objects.select_related(
            "assignee", "dept_assignment"
        )
        .filter(session_id=session_id)
        .order_by("display_order", "created_at")
    )


def get_overdue_commitments(*, session_id: int = None):
    """
    Cam kết quá deadline và chưa hoàn thành.
    Dùng để hiện cảnh báo trên dashboard pipeline.
    """
    qs = MeetingCommitment.objects.select_related(
        "assignee", "session", "dept_assignment"
    ).filter(
        status=CommitmentStatus.OPEN,
        deadline__lt=timezone.now().date(),
    )

    if session_id:
        qs = qs.filter(session_id=session_id)

    return qs.order_by("deadline")
