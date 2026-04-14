"""
helpdesk/services/ticket_service.py
=====================================
Write operations cho hệ thống ticket IT.

Quy tắc:
- Khi tạo ticket → tự động tạo Task liên kết (stage=TODO, tags="IT Ticket")
- Khi IT thay đổi status → đồng bộ Task stage tương ứng
- Khi đóng ticket → Task chuyển DONE, không ai gửi thêm được
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.helpdesk.models import (
    Ticket, TicketAttachment, TicketMessage, TicketPriority,
    TicketStatus, TICKET_STATUS_TO_TASK_STAGE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _system_message(ticket: Ticket, event_type: str, detail: dict, text: str) -> TicketMessage:
    return TicketMessage.objects.create(
        ticket=ticket,
        sender=None,
        body=text,
        is_system_event=True,
        event_type=event_type,
        event_detail=detail,
    )


def _sync_task_stage(ticket: Ticket, actor) -> None:
    """Đồng bộ stage của Task liên kết theo status của ticket."""
    if not ticket.linked_task_id:
        return
    try:
        from apps.tasks.services.task_service import move_stage as task_move_stage
        from apps.tasks.models import Task
        task = Task.objects.get(pk=ticket.linked_task_id)
        new_stage = TICKET_STATUS_TO_TASK_STAGE.get(ticket.status, "TODO")
        if task.stage != new_stage:
            task_move_stage(actor=actor, task=task, new_stage=new_stage)
    except Exception:
        pass  # Không để lỗi task ảnh hưởng luồng ticket


def _create_linked_task(ticket: Ticket, actor) -> None:
    """Tạo Task tự động khi ticket được mở."""
    try:
        from apps.tasks.services.task_service import create_task
        from apps.tasks.policies import TaskPolicy

        # Tìm IT Admin users để assign
        from apps.helpdesk.policies import HelpdeskPolicy
        it_users = list(HelpdeskPolicy.get_it_users())
        assignee_id = it_users[0].id if it_users else None

        # Ưu tiên assign cho ticket.assigned_to nếu đã có
        if ticket.assigned_to_id:
            assignee_id = ticket.assigned_to_id

        priority_map = {
            TicketPriority.LOW:    "LOW",
            TicketPriority.MEDIUM: "MEDIUM",
            TicketPriority.HIGH:   "HIGH",
            TicketPriority.URGENT: "URGENT",
        }

        task = create_task(
            actor=actor,
            title=f"[IT Ticket #{ticket.pk}] {ticket.subject}",
            description=(
                f"Ticket yêu cầu IT từ {actor.get_full_name() or actor.username}.\n"
                f"Loại: {ticket.category_label}\n"
                f"Xem chi tiết: /helpdesk/{ticket.pk}/"
            ),
            assignee_id=assignee_id,
            priority=priority_map.get(ticket.priority, "MEDIUM"),
            tags="IT Ticket",
        )
        ticket.linked_task = task
        ticket.save(update_fields=["linked_task"])
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Services
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def create_ticket(
    *,
    actor,
    subject: str,
    body: str,
    category: str,
    priority: str = TicketPriority.MEDIUM,
    files: list | None = None,
) -> Ticket:
    ticket = Ticket.objects.create(
        subject=subject.strip(),
        category=category,
        priority=priority,
        status=TicketStatus.OPEN,
        created_by=actor,
    )

    # Tin nhắn đầu tiên từ người tạo
    msg = TicketMessage.objects.create(
        ticket=ticket,
        sender=actor,
        body=body.strip(),
    )

    # Xử lý file đính kèm
    if files:
        _save_attachments(ticket, msg, actor, files)

    # Ghi sự kiện mở ticket
    _system_message(
        ticket, "TICKET_OPENED",
        {"by": actor.get_full_name() or actor.username},
        f"Ticket được mở bởi {actor.get_full_name() or actor.username}.",
    )

    # Tạo Task liên kết
    _create_linked_task(ticket, actor)

    return ticket


@transaction.atomic
def reply_ticket(
    *,
    actor,
    ticket: Ticket,
    body: str,
    files: list | None = None,
) -> TicketMessage:
    msg = TicketMessage.objects.create(
        ticket=ticket,
        sender=actor,
        body=body.strip(),
    )
    if files:
        _save_attachments(ticket, msg, actor, files)
    ticket.updated_at = timezone.now()
    ticket.save(update_fields=["updated_at"])
    return msg


@transaction.atomic
def change_status(
    *,
    actor,
    ticket: Ticket,
    new_status: str,
    note: str = "",
) -> Ticket:
    old_status = ticket.status
    ticket.status = new_status
    ticket.updated_at = timezone.now()
    ticket.save(update_fields=["status", "updated_at"])

    label_map = dict(TicketStatus.choices)
    detail_text = (
        f"Trạng thái chuyển từ «{label_map.get(old_status)}» → «{label_map.get(new_status)}»"
    )
    if note:
        detail_text += f"\nGhi chú: {note}"

    _system_message(
        ticket, "STATUS_CHANGED",
        {"from": old_status, "to": new_status, "by": actor.get_full_name() or actor.username},
        detail_text,
    )

    # Đồng bộ Task stage
    _sync_task_stage(ticket, actor)

    return ticket


@transaction.atomic
def close_ticket(*, actor, ticket: Ticket, note: str = "") -> Ticket:
    ticket.status = TicketStatus.CLOSED
    ticket.closed_by = actor
    ticket.closed_at = timezone.now()
    ticket.updated_at = timezone.now()
    ticket.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])

    closer_name = actor.get_full_name() or actor.username
    detail_text = f"Ticket đã được {closer_name} xác nhận hoàn thành và đóng lại."
    if note:
        detail_text += f"\nGhi chú cuối: {note}"

    _system_message(
        ticket, "TICKET_CLOSED",
        {"by": closer_name},
        detail_text,
    )

    _sync_task_stage(ticket, actor)
    return ticket


@transaction.atomic
def assign_ticket(*, actor, ticket: Ticket, assignee) -> Ticket:
    old_assignee = ticket.assigned_to
    ticket.assigned_to = assignee
    ticket.updated_at = timezone.now()
    ticket.save(update_fields=["assigned_to", "updated_at"])

    assignee_name = assignee.get_full_name() or assignee.username if assignee else "—"
    _system_message(
        ticket, "ASSIGNED",
        {"to": assignee_name},
        f"Ticket được giao cho {assignee_name}.",
    )

    # Đồng bộ Task assignee
    if ticket.linked_task_id and assignee:
        try:
            from apps.tasks.services.task_service import assign_task
            from apps.tasks.models import Task
            task = Task.objects.get(pk=ticket.linked_task_id)
            assign_task(actor=actor, task=task, assignee_id=assignee.id)
        except Exception:
            pass

    return ticket


def _save_attachments(ticket: Ticket, msg: TicketMessage, actor, files: list) -> None:
    for f in files:
        if not f or not f.name:
            continue
        att = TicketAttachment.objects.create(
            ticket=ticket,
            message=msg,
            uploaded_by=actor,
            file=f,
            filename=f.name,
            file_size=f.size,
            content_type=getattr(f, "content_type", ""),
        )
        # Thêm vào attachments_json của message để render nhanh
        msg.attachments_json.append({
            "id": att.pk,
            "name": att.filename,
            "url": att.file.url,
            "size": att.file_size,
            "size_display": att.size_display,
        })
    msg.save(update_fields=["attachments_json"])
