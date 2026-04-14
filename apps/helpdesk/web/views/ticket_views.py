"""
helpdesk/web/views/ticket_views.py
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.helpdesk.models import Ticket, TicketCategory, TicketPriority, TicketStatus
from apps.helpdesk.policies import HelpdeskPolicy
from apps.helpdesk.selectors.ticket_selectors import get_tickets_for_user
from apps.helpdesk.services.ticket_service import (
    assign_ticket, change_status, close_ticket, create_ticket, reply_ticket,
)


LOGIN_URL = "authentication:staff_login"


# ─────────────────────────────────────────────────────────────────────────────
# Ticket List
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def ticket_list(request):
    user = request.user

    if not (HelpdeskPolicy.can_create_ticket(user) or HelpdeskPolicy.can_view_all_tickets(user)):
        return HttpResponseForbidden()

    filters = {
        "status":   request.GET.get("status") or None,
        "priority": request.GET.get("priority") or None,
        "category": request.GET.get("category") or None,
        "search":   request.GET.get("q") or None,
    }

    tickets = get_tickets_for_user(user, filters=filters)
    open_count = tickets.exclude(status=TicketStatus.CLOSED).count()

    return render(request, "helpdesk/staff/ticket_list.html", {
        "tickets":        tickets,
        "open_count":     open_count,
        "filters":        filters,
        "statuses":       TicketStatus.choices,
        "priorities":     TicketPriority.choices,
        "categories":     TicketCategory.choices,
        "can_create":     HelpdeskPolicy.can_create_ticket(user),
        "is_it_admin":    HelpdeskPolicy.is_it_admin(user),
        "view_all":       HelpdeskPolicy.can_view_all_tickets(user),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Ticket Create
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def ticket_create(request):
    user = request.user
    if not HelpdeskPolicy.can_create_ticket(user):
        return HttpResponseForbidden()

    if request.method == "POST":
        subject  = (request.POST.get("subject") or "").strip()
        body     = (request.POST.get("body") or "").strip()
        category = request.POST.get("category") or TicketCategory.OTHER
        priority = request.POST.get("priority") or TicketPriority.MEDIUM
        files    = request.FILES.getlist("attachments")

        if not subject or not body:
            messages.error(request, "Vui lòng nhập tiêu đề và nội dung yêu cầu.")
        else:
            ticket = create_ticket(
                actor=user,
                subject=subject,
                body=body,
                category=category,
                priority=priority,
                files=files or None,
            )
            messages.success(request, f"Đã gửi ticket #{ticket.pk} thành công.")
            return redirect("helpdesk:detail", ticket_id=ticket.pk)

    return render(request, "helpdesk/staff/ticket_create.html", {
        "categories": TicketCategory.choices,
        "priorities": TicketPriority.choices,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Ticket Detail
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def ticket_detail(request, ticket_id):
    user = request.user
    ticket = get_object_or_404(
        Ticket.objects.select_related("created_by", "assigned_to", "closed_by", "linked_task")
                      .prefetch_related("messages__sender", "messages__attachment_files"),
        pk=ticket_id,
    )

    if not HelpdeskPolicy.can_view_ticket(user, ticket):
        return HttpResponseForbidden()

    can_reply         = HelpdeskPolicy.can_reply(user, ticket)
    can_change_status = HelpdeskPolicy.can_change_status(user, ticket)
    can_close         = HelpdeskPolicy.can_close_ticket(user, ticket)
    can_assign        = HelpdeskPolicy.can_assign(user)
    is_it_admin       = HelpdeskPolicy.is_it_admin(user)
    it_users          = list(HelpdeskPolicy.get_it_users()) if can_assign else []

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Reply ──────────────────────────────────────────────────────────
        if action == "reply" and can_reply:
            body  = (request.POST.get("body") or "").strip()
            files = request.FILES.getlist("attachments")
            if not body and not files:
                messages.error(request, "Vui lòng nhập nội dung hoặc đính kèm tệp.")
            else:
                reply_ticket(actor=user, ticket=ticket, body=body, files=files or None)
                messages.success(request, "Đã gửi phản hồi.")
            return redirect("helpdesk:detail", ticket_id=ticket.pk)

        # ── Change status (IT Admin) ───────────────────────────────────────
        if action == "change_status" and can_change_status:
            new_status = request.POST.get("status")
            note       = (request.POST.get("note") or "").strip()
            if new_status in dict(TicketStatus.choices):
                change_status(actor=user, ticket=ticket, new_status=new_status, note=note)
                messages.success(request, f"Đã chuyển trạng thái: {dict(TicketStatus.choices)[new_status]}")
            return redirect("helpdesk:detail", ticket_id=ticket.pk)

        # ── Close (Executive confirms) ─────────────────────────────────────
        if action == "close" and can_close:
            note = (request.POST.get("close_note") or "").strip()
            close_ticket(actor=user, ticket=ticket, note=note)
            messages.success(request, "Ticket đã được đóng và xác nhận hoàn thành.")
            return redirect("helpdesk:detail", ticket_id=ticket.pk)

        # ── Assign (IT Admin) ──────────────────────────────────────────────
        if action == "assign" and can_assign:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            aid = request.POST.get("assignee_id")
            assignee = User.objects.filter(pk=aid).first() if aid else None
            assign_ticket(actor=user, ticket=ticket, assignee=assignee)
            messages.success(request, "Đã cập nhật IT phụ trách.")
            return redirect("helpdesk:detail", ticket_id=ticket.pk)

    return render(request, "helpdesk/staff/ticket_detail.html", {
        "ticket":           ticket,
        "messages_qs":      ticket.messages.all(),
        "can_reply":        can_reply,
        "can_change_status": can_change_status,
        "can_close":        can_close,
        "can_assign":       can_assign,
        "is_it_admin":      is_it_admin,
        "it_users":         it_users,
        "statuses":         TicketStatus.choices,
        "all_statuses":     dict(TicketStatus.choices),
    })
