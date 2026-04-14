"""
notifications.services.push
────────────────────────────
API duy nhất để các service layer (approvals, contract, scheduling...)
gửi thông báo. Các app đó KHÔNG import gì khác từ notifications.

Cách dùng:
    from apps.notifications.services.push import push

    push(
        recipients=user,                  # User | QuerySet[User] | list[User]
        event_type=EventType.APPROVAL_APPROVED,
        level="success",
        title="Báo giá đã được duyệt",
        body="Báo giá Công ty ABC đã được Manager Nguyễn Văn A phê duyệt.",
        url="/approvals/5/",
    )

Luồng:
    1. Lưu Notification vào PostgreSQL
    2. Broadcast qua Redis → WebSocket → browser của recipient
"""

from __future__ import annotations

from typing import Union

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model

from apps.notifications.models import EventType, Notification, NotificationLevel

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_user_list(recipients) -> list:
    """Chuẩn hoá recipients thành list[User]."""
    if recipients is None:
        return []
    if isinstance(recipients, User):
        return [recipients]
    # QuerySet hoặc list
    return list(recipients)


def _channel_name(user_id: int) -> str:
    """
    Tên channel group cho mỗi user.
    Consumer subscribe vào group này khi connect WebSocket.
    """
    return f"user_notif_{user_id}"


def _broadcast(notification: Notification) -> None:
    """Gửi notification qua channel layer tới WebSocket của user."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            _channel_name(notification.recipient_id),
            {
                "type":         "notify",           # → consumer.notify()
                "notification": notification.as_dict(),
            },
        )
    except Exception:
        # Không để broadcast failure rollback DB transaction
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def push(
    *,
    recipients: Union[User, list, "QuerySet"],
    event_type: str,
    title: str,
    body: str = "",
    url: str = "",
    level: str = NotificationLevel.INFO,
    meta: dict | None = None,
) -> list[Notification]:
    """
    Tạo + broadcast thông báo cho một hoặc nhiều user.

    recipients  -- User instance, list[User], hoặc QuerySet[User]
    event_type  -- EventType constant (vd: EventType.APPROVAL_APPROVED)
    title       -- Tiêu đề hiển thị trên notification popup
    body        -- Nội dung chi tiết (tuỳ chọn)
    url         -- URL mà người dùng sẽ được chuyển tới khi click
    level       -- "info" | "success" | "warning" | "danger"
    meta        -- Dict metadata tuỳ ý để lưu thêm context

    Trả về list các Notification đã tạo.
    """
    users = _to_user_list(recipients)
    if not users:
        return []

    created = []
    for user in users:
        notif = Notification.objects.create(
            recipient=user,
            event_type=event_type,
            level=level,
            title=title,
            body=body,
            url=url,
            meta=meta or {},
        )
        _broadcast(notif)
        created.append(notif)

    return created


# ── Convenience helpers cho các event phổ biến ───────────────────────────────

def push_to_managers(
    *,
    event_type: str,
    title: str,
    body: str = "",
    url: str = "",
    level: str = NotificationLevel.INFO,
    exclude_user=None,
) -> list[Notification]:
    """Gửi thông báo cho tất cả Manager (và superuser)."""
    qs = User.objects.filter(
        groups__name__in=["Managers", "Manager"],
        is_active=True,
    ).distinct()
    if exclude_user:
        qs = qs.exclude(pk=exclude_user.pk)
    return push(
        recipients=qs,
        event_type=event_type,
        title=title,
        body=body,
        url=url,
        level=level,
    )
