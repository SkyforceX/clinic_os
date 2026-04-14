"""
helpdesk/selectors/ticket_selectors.py
"""
from __future__ import annotations

from apps.helpdesk.models import Ticket, TicketStatus
from apps.helpdesk.policies import HelpdeskPolicy


def get_tickets_for_user(user, filters: dict | None = None):
    """QuerySet ticket theo quyền + bộ lọc."""
    if HelpdeskPolicy.can_view_all_tickets(user):
        qs = Ticket.objects.all()
    else:
        qs = Ticket.objects.filter(created_by=user)

    qs = qs.select_related("created_by", "assigned_to", "closed_by")

    if filters:
        if filters.get("status"):
            qs = qs.filter(status=filters["status"])
        if filters.get("priority"):
            qs = qs.filter(priority=filters["priority"])
        if filters.get("category"):
            qs = qs.filter(category=filters["category"])
        q = filters.get("search")
        if q:
            qs = qs.filter(subject__icontains=q)

    return qs.order_by("-created_at")


def get_ticket_counts(user) -> dict:
    """Đếm ticket theo status để hiển thị trên sidebar / dashboard."""
    qs = get_tickets_for_user(user)
    counts = {s: 0 for s in TicketStatus.values}
    for row in qs.values("status").annotate(n=__import__("django.db.models", fromlist=["Count"]).Count("id")):
        counts[row["status"]] = row["n"]
    return counts


def get_open_ticket_count(user) -> int:
    """Số ticket đang mở (OPEN + IN_PROGRESS + PENDING_CONFIRM)."""
    qs = get_tickets_for_user(user)
    return qs.exclude(status=TicketStatus.CLOSED).count()
