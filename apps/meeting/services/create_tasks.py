"""
Bridge service: meeting → tasks.

Được gọi tự động bởi close_session() sau khi đóng họp.
Tạo tasks.Task cho mỗi MeetingCommitment chưa có task,
rồi backfill commitment.task FK để hai phía liên kết với nhau.

Dùng apps.get_model() để tránh circular import.
"""
from django.apps import apps
from django.db import transaction

from apps.meeting.domain.enums import CommitmentStatus
from apps.meeting.models import MeetingCommitment, MeetingSession


@transaction.atomic
def create_tasks_from_session(*, session: MeetingSession) -> list:
    """
    Bulk-create tasks.Task từ tất cả MeetingCommitment của session.
    Idempotent: chỉ tạo cho commitment chưa có task (task_id IS NULL).
    Returns: list[Task] vừa tạo.
    """
    Task = apps.get_model("tasks", "Task")

    commitments = list(
        MeetingCommitment.objects.filter(
            session=session,
            task__isnull=True,
            status=CommitmentStatus.OPEN,
        ).select_related("assignee", "dept_assignment")
    )

    if not commitments:
        return []

    # Tạo Task objects — map đúng field của tasks.Task
    task_objs = []
    for c in commitments:
        # tags gắn tên session + phòng ban để truy vết
        dept_label = c.dept_assignment.get_department_display() if c.dept_assignment else ""
        tags_parts = [f"họp:{session.pk}"]
        if dept_label:
            tags_parts.append(dept_label)

        task_objs.append(Task(
            title       = c.title,
            description = (
                c.description
                or f"Cam kết từ buổi họp: {session.title} ({session.meeting_date})"
            ),
            stage       = "TODO",
            priority    = _map_priority(c),
            created_by  = session.created_by,
            assignee    = c.assignee,
            due_date    = c.deadline,
            tags        = ", ".join(tags_parts),
        ))

    created_tasks = Task.objects.bulk_create(task_objs, batch_size=100)

    # Backfill commitment.task FK
    for commitment, task in zip(commitments, created_tasks):
        commitment.task = task
    MeetingCommitment.objects.bulk_update(commitments, ["task"], batch_size=100)

    return created_tasks


def _map_priority(commitment: MeetingCommitment) -> str:
    """Deadline đã qua → HIGH, sắp tới 3 ngày → HIGH, còn lại MEDIUM."""
    if commitment.is_overdue:
        return "HIGH"
    if commitment.deadline:
        from datetime import date
        days_left = (commitment.deadline - date.today()).days
        if days_left <= 3:
            return "HIGH"
    return "MEDIUM"
