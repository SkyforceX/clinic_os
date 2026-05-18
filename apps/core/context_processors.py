from django.conf import settings


def runtime_flags(request):
    return {
        "notifications_ws_enabled": bool(getattr(settings, "NOTIFICATIONS_WS_ENABLED", False)),
    }
