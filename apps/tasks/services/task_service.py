from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.tasks.models import Task, TaskActivity, TaskComment, TaskPriority, TaskStage


def _log(task: Task, actor, action: str, detail: dict = None) -> None:
    TaskActivity.objects.create(task=task, actor=actor, action=action, detail=detail or {})


@transaction.atomic
def create_task(
    *,
    actor,
    title: str,
    description: str = "",
    assignee_id: int | None = None,
    priority: str = TaskPriority.MEDIUM,
    due_date: date | None = None,
    start_date: date | None = None,
    estimated_hours: Decimal | None = None,
    tags: str = "",
    watcher_ids: list[int] | None = None,
) -> Task:
    task = Task.objects.create(
        title=title.strip(),
        description=description.strip(),
        created_by=actor,
        assignee_id=assignee_id,
        priority=priority,
        stage=TaskStage.TODO,
        due_date=due_date,
        start_date=start_date,
        estimated_hours=estimated_hours,
        tags=tags,
    )
    if watcher_ids:
        task.watchers.set(watcher_ids)
    _log(task, actor, TaskActivity.Action.CREATED, {"title": title})
    return task


@transaction.atomic
def update_task(*, actor, task: Task, **fields) -> Task:
    changed = {}
    for key, val in fields.items():
        if hasattr(task, key) and getattr(task, key) != val:
            changed[key] = {"from": str(getattr(task, key)), "to": str(val)}
            setattr(task, key, val)
    if changed:
        task.save()
        _log(task, actor, TaskActivity.Action.UPDATED, changed)
    return task


@transaction.atomic
def move_stage(*, actor, task: Task, new_stage: str) -> Task:
    old = task.stage
    task.stage = new_stage
    if new_stage == TaskStage.DONE and not task.completed_at:
        task.completed_at = timezone.now()
    elif new_stage != TaskStage.DONE:
        task.completed_at = None
    task.save(update_fields=["stage", "completed_at", "updated_at"])
    _log(task, actor, TaskActivity.Action.MOVED, {"from": old, "to": new_stage})
    return task


@transaction.atomic
def assign_task(*, actor, task: Task, assignee_id: int | None) -> Task:
    old_id = task.assignee_id
    task.assignee_id = assignee_id
    task.save(update_fields=["assignee_id", "updated_at"])
    _log(task, actor, TaskActivity.Action.ASSIGNED, {"from": old_id, "to": assignee_id})
    return task


@transaction.atomic
def add_comment(*, actor, task: Task, body: str, is_internal: bool = False) -> TaskComment:
    comment = TaskComment.objects.create(
        task=task, author=actor, body=body.strip(), is_internal=is_internal,
    )
    _log(task, actor, TaskActivity.Action.COMMENTED, {"preview": body[:100]})
    return comment


@transaction.atomic
def delete_task(*, actor, task: Task) -> None:
    task.delete()
