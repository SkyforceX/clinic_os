"""
Bridge service: meeting → tasks.

Được gọi tự động bởi close_session() sau khi đóng họp.
Tạo tasks.Task cho mỗi MeetingCommitment chưa có task,
rồi backfill commitment.task FK để hai phía liên kết với nhau.

Import tasks app theo string để tránh circular dependency
(tasks app sẽ import meeting để hiện context — không được import ngược).
"""
from django.apps import apps
from django.db import transaction

from apps.meeting.domain.enums import CommitmentStatus
from apps.meeting.models import MeetingCommitment, MeetingSession


@transaction.atomic
def create_tasks_from_session(*, session: MeetingSession) -> list:
    """
    Bulk-create tasks.Task từ tất cả MeetingCommitment của session.
    Chỉ tạo cho commitment chưa có task (idempotent nếu gọi lại).

    Returns: list[Task] vừa được tạo.
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

    # Tạo Task objects (chưa save)
    task_objs = [
        Task(
            title=c.title,
            description=c.description or "",
            department=c.dept_assignment.department if c.dept_assignment else "other",
            status="TODO",
            priority=_map_priority(c),
            assignee=c.assignee,
            reporter=session.created_by,
            deadline=c.deadline,
            related_contract=session.contract,
            # source_commitment được set sau khi save (vì cần PK của task)
        )
        for c in commitments
    ]

    created_tasks = Task.objects.bulk_create(task_objs, batch_size=100)

    # Backfill commitment.task FK
    commitment_updates = []
    for commitment, task in zip(commitments, created_tasks):
        commitment.task = task
        commitment_updates.append(commitment)

    MeetingCommitment.objects.bulk_update(commitment_updates, ["task"], batch_size=100)

    # Ghi TaskStatusLog ban đầu nếu app tasks có model này
    _try_create_status_logs(created_tasks, actor=session.created_by)

    return created_tasks


def _map_priority(commitment: MeetingCommitment) -> str:
    """
    Mapping đơn giản: commitment quá hạn → HIGH, còn lại → MEDIUM.
    Có thể mở rộng sau dựa trên trường priority của commitment.
    """
    if commitment.is_overdue:
        return "HIGH"
    return "MEDIUM"


def _try_create_status_logs(tasks, *, actor) -> None:
    """
    Tạo TaskStatusLog ban đầu (TODO) nếu model tồn tại.
    Wrapped trong try/except để không break nếu tasks app chưa migrate.
    """
    try:
        TaskStatusLog = apps.get_model("tasks", "TaskStatusLog")
        TaskStatusLog.objects.bulk_create(
            [
                TaskStatusLog(
                    task=task,
                    changed_by=actor,
                    from_status="",
                    to_status="TODO",
                )
                for task in tasks
            ],
            batch_size=100,
        )
    except LookupError:
        pass
