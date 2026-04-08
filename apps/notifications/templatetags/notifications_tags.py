from django import template

from apps.notifications.models import Notification

register = template.Library()


@register.simple_tag(takes_context=True)
def unread_notification_count(context):
    """
    Trả về số Notification chưa đọc của user hiện tại.
    Dùng trong template:
        {% load notifications_tags %}
        {% unread_notification_count as cnt %}
        {{ cnt }}
    """
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return 0
    return Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
