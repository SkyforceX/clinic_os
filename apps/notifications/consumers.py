"""
NotificationConsumer
─────────────────────
WebSocket consumer — mỗi browser tab mở 1 connection.
Consumer tự join vào group "user_notif_{user_id}" khi connect.
Khi push() gọi group_send → consumer nhận → gửi JSON xuống browser.
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")

        # Từ chối anonymous
        if not user or not user.is_authenticated:
            await self.close(code=4003)
            return

        self.group_name = f"user_notif_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ── Nhận message từ group_send (server → consumer) ────────────────────────
    async def notify(self, event):
        """
        Handler cho type="notify" từ push._broadcast().
        Gửi payload JSON xuống WebSocket client.
        """
        await self.send(text_data=json.dumps({
            "type":         "notification",
            "notification": event["notification"],
        }))

    # ── Nhận message từ browser (browser → server) ────────────────────────────
    async def receive(self, text_data=None, bytes_data=None):
        """
        Browser có thể gửi {"type": "mark_read", "ids": [1, 2, 3]}
        để đánh dấu đã đọc mà không cần HTTP request.
        """
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get("type") == "mark_read":
            ids = data.get("ids", [])
            if ids:
                # Chạy ORM trong sync thread
                from asgiref.sync import sync_to_async
                from apps.notifications.models import Notification

                user = self.scope["user"]
                await sync_to_async(
                    lambda: Notification.objects
                    .filter(recipient=user, pk__in=ids)
                    .update(is_read=True)
                )()
