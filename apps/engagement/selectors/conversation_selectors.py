from django.db.models import Count, Q
from django.utils import timezone


def get_inbox_conversations(user, status=None, channel_id=None, assigned_to_me=False,
                            search=None, limit=40, offset=0):
    from apps.engagement.models import Conversation
    qs = (
        Conversation.objects
        .select_related("channel", "assigned_to", "linked_contact", "linked_company")
        .prefetch_related("tags")
        .order_by("-last_message_at")
    )
    if status:
        qs = qs.filter(status=status)
    if channel_id:
        qs = qs.filter(channel_id=channel_id)
    if assigned_to_me:
        qs = qs.filter(assigned_to=user)
    if search:
        qs = qs.filter(
            Q(customer_name__icontains=search)
            | Q(subject__icontains=search)
            | Q(external_id__icontains=search)
        )
    total = qs.count()
    return qs[offset:offset + limit], total


def get_conversation_with_messages(conv_id):
    from apps.engagement.models import Conversation
    return (
        Conversation.objects
        .select_related("channel", "assigned_to", "linked_contact", "linked_company")
        .prefetch_related("tags", "messages__sender_agent")
        .get(pk=conv_id)
    )


def get_unread_count(user):
    from apps.engagement.models import Conversation, Message
    return (
        Message.objects
        .filter(direction="IN", is_read=False, conversation__assigned_to=user)
        .values("conversation_id")
        .distinct()
        .count()
    )


def get_care_stats(days: int = 30):
    from apps.engagement.models import Conversation, Message
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=days)

    total_convs   = Conversation.objects.filter(created_at__gte=cutoff).count()
    open_convs    = Conversation.objects.filter(status="OPEN").count()
    resolved      = Conversation.objects.filter(status="RESOLVED", resolved_at__gte=cutoff).count()

    # Avg first reply time (minutes)
    replied = Conversation.objects.filter(
        first_reply_at__isnull=False,
        created_at__gte=cutoff,
    ).values_list("created_at","first_reply_at")
    reply_times = [(r - c).total_seconds() / 60 for c, r in replied if r > c]
    avg_reply_min = round(sum(reply_times) / len(reply_times), 1) if reply_times else None

    # CSAT average
    from django.db.models import Avg
    csat = Conversation.objects.filter(
        csat_score__isnull=False,
        resolved_at__gte=cutoff,
    ).aggregate(avg=Avg("csat_score"))["avg"]

    return {
        "total_conversations": total_convs,
        "open_conversations":  open_convs,
        "resolved_conversations": resolved,
        "avg_first_reply_min": avg_reply_min,
        "csat_avg": round(float(csat), 2) if csat else None,
        "days": days,
    }
