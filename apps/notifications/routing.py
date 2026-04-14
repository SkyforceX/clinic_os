from django.urls import path

from apps.notifications.consumers import NotificationConsumer

websocket_urlpatterns = [
    # ws://host/ws/notifications/
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
