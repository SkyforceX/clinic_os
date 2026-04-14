import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.engagement.models import CannedResponse, ChannelConfig, Conversation, Message
from apps.engagement.policies import EngagementPolicy
from apps.engagement.selectors.conversation_selectors import (
    get_care_stats,
    get_conversation_with_messages,
    get_inbox_conversations,
    get_unread_count,
)
from apps.engagement.services.channel_service import send_reply


def _deny(request):
    if not EngagementPolicy.is_agent(request.user):
        return HttpResponseForbidden("<h2>403 – Không có quyền truy cập Engagement.</h2>")
    return None


@login_required(login_url="authentication:staff_login")
def inbox(request):
    denied = _deny(request)
    if denied:
        return denied

    status_filter    = request.GET.get("status", "OPEN")
    channel_id       = request.GET.get("channel") or None
    assigned_to_me   = request.GET.get("mine") == "1"
    search           = request.GET.get("q") or None
    conv_id          = request.GET.get("conv") or None

    conversations, total = get_inbox_conversations(
        user=request.user,
        status=status_filter if status_filter != "ALL" else None,
        channel_id=channel_id,
        assigned_to_me=assigned_to_me,
        search=search,
    )

    active_conv = None
    if conv_id:
        try:
            active_conv = get_conversation_with_messages(conv_id)
            # Mark incoming messages as read
            active_conv.messages.filter(direction="IN", is_read=False).update(is_read=True)
        except Conversation.DoesNotExist:
            pass

    channels       = ChannelConfig.objects.filter(status="ACTIVE").order_by("channel_type", "name")
    canned         = CannedResponse.objects.all()[:20]
    unread_count   = get_unread_count(request.user)
    can_assign     = EngagementPolicy.can_assign_contacts(request.user)

    from django.contrib.auth import get_user_model
    agents = []
    if can_assign:
        User = get_user_model()
        agents = list(User.objects.filter(
            groups__name__in=["Engagement Agent","Engagement Team","Engagement Lead","Managers","Manager"]
        ).distinct().order_by("first_name","username"))

    return render(request, "engagement/staff/inbox.html", {
        "conversations":  conversations,
        "total":          total,
        "active_conv":    active_conv,
        "channels":       channels,
        "canned":         canned,
        "unread_count":   unread_count,
        "can_assign":     can_assign,
        "agents":         agents,
        "status_filter":  status_filter,
        "channel_filter": channel_id,
        "search":         search,
        "assigned_to_me": assigned_to_me,
        "is_engagement_admin":  EngagementPolicy.is_engagement_admin(request.user),
        "STATUS_CHOICES": Conversation.Status.choices,
    })


@login_required(login_url="authentication:staff_login")
@require_POST
def send_message(request, conv_id):
    denied = _deny(request)
    if denied:
        return denied

    conv = get_object_or_404(Conversation, pk=conv_id)
    body = json.loads(request.body)
    text = (body.get("text") or "").strip()
    is_internal = bool(body.get("is_internal", False))

    if not text:
        return JsonResponse({"ok": False, "error": "Empty message"}, status=400)

    msg = send_reply(conv, text, agent=request.user, is_internal=is_internal)
    return JsonResponse({
        "ok":        True,
        "msg_id":    msg.id,
        "sent_at":   msg.sent_at.isoformat(),
        "direction": msg.direction,
        "content":   msg.content,
        "agent_name": request.user.get_full_name() or request.user.username,
        "is_internal": msg.is_internal,
    })


@login_required(login_url="authentication:staff_login")
@require_POST
def update_conversation(request, conv_id):
    denied = _deny(request)
    if denied:
        return denied

    conv = get_object_or_404(Conversation, pk=conv_id)
    body = json.loads(request.body)

    update_fields = []
    if "status" in body:
        conv.status = body["status"]
        update_fields.append("status")
        if body["status"] == "RESOLVED":
            from django.utils import timezone
            conv.resolved_at = timezone.now()
            update_fields.append("resolved_at")

    if "priority" in body:
        conv.priority = body["priority"]
        update_fields.append("priority")

    if "assigned_to_id" in body:
        if EngagementPolicy.can_assign_contacts(request.user):
            conv.assigned_to_id = body["assigned_to_id"] or None
            update_fields.append("assigned_to_id")

    if "subject" in body:
        conv.subject = body["subject"]
        update_fields.append("subject")

    if "internal_note" in body:
        conv.internal_note = body["internal_note"]
        update_fields.append("internal_note")

    if "csat_score" in body:
        conv.csat_score = body["csat_score"]
        update_fields.append("csat_score")

    if update_fields:
        conv.save(update_fields=update_fields)

    return JsonResponse({"ok": True})


@login_required(login_url="authentication:staff_login")
def poll_messages(request, conv_id):
    """Polling để lấy tin nhắn mới cho inbox."""
    denied = _deny(request)
    if denied:
        return denied

    conv     = get_object_or_404(Conversation, pk=conv_id)
    after_id = int(request.GET.get("after_id", 0))

    msgs = Message.objects.filter(
        conversation=conv,
        id__gt=after_id,
    ).select_related("sender_agent").values(
        "id","direction","content","msg_type","sent_at","is_internal",
        "sender_agent__first_name","sender_agent__last_name","sender_agent__username",
    )

    Message.objects.filter(conversation=conv, direction="IN", is_read=False).update(is_read=True)

    def agent_name(m):
        fn = m.get("sender_agent__first_name") or ""
        ln = m.get("sender_agent__last_name") or ""
        return (f"{fn} {ln}".strip() or m.get("sender_agent__username") or "Agent")

    return JsonResponse({
        "messages": [
            {
                "id":          m["id"],
                "direction":   m["direction"],
                "content":     m["content"],
                "type":        m["msg_type"],
                "sent_at":     m["sent_at"].isoformat(),
                "is_internal": m["is_internal"],
                "agent_name":  agent_name(m),
            }
            for m in msgs
        ],
        "conv_status": conv.status,
    })
