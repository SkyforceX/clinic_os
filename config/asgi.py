"""
ASGI config for clinic_os.

Thay thế wsgi.py khi chạy với Daphne hoặc Uvicorn.

Local  (Windows + Docker Redis):
    daphne clinic_os.asgi:application
    hoặc: python manage.py runserver  (Django 4.2+ tự detect ASGI nếu có channels)

Ubuntu production:
    daphne -b 0.0.0.0 -p 8000 clinic_os.asgi:application
    (hoặc Gunicorn + uvicorn workers: gunicorn clinic_os.asgi:application -k uvicorn.workers.UvicornWorker)
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Khởi tạo Django trước khi import channels
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from apps.notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        # HTTP requests → Django view layer bình thường
        "http": django_asgi_app,
        # WebSocket → Channels consumer
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
