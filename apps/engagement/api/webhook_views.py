"""
engagement/api/webhook_views.py
==========================
Endpoints nhận webhook từ Zalo OA, Facebook Messenger, và WebChat widget.
Không yêu cầu Django login — xác thực bằng signature/token.
"""
import json
import uuid as uuid_lib

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.engagement.models import ChannelConfig


def _get_channel(channel_type: str, pk: int):
    try:
        return ChannelConfig.objects.get(pk=pk, channel_type=channel_type, status="ACTIVE")
    except ChannelConfig.DoesNotExist:
        return None


# ── Zalo OA Webhook ────────────────────────────────────────────────────────────

@csrf_exempt
def zalo_webhook(request, channel_id: int):
    channel = _get_channel("ZALO", channel_id)
    if not channel:
        return HttpResponse("Not found", status=404)

    if request.method == "GET":
        # Zalo verify endpoint
        return HttpResponse(request.GET.get("hub.challenge", "ok"))

    if request.method == "POST":
        from apps.engagement.services.channel_service import handle_zalo_webhook, verify_zalo_webhook
        if not verify_zalo_webhook(channel, request):
            return HttpResponse("Forbidden", status=403)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse("Bad request", status=400)
        handle_zalo_webhook(channel, payload)
        return HttpResponse("ok")

    return HttpResponse("Method not allowed", status=405)


# ── Facebook Messenger Webhook ─────────────────────────────────────────────────

@csrf_exempt
def messenger_webhook(request, channel_id: int):
    channel = _get_channel("MESSENGER", channel_id)
    if not channel:
        return HttpResponse("Not found", status=404)

    if request.method == "GET":
        # Facebook verify handshake
        mode      = request.GET.get("hub.mode")
        token     = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == channel.fb_verify_token:
            return HttpResponse(challenge)
        return HttpResponse("Forbidden", status=403)

    if request.method == "POST":
        from apps.engagement.services.channel_service import handle_messenger_webhook, verify_fb_webhook
        if not verify_fb_webhook(channel, request):
            return HttpResponse("Forbidden", status=403)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse("Bad request", status=400)
        if payload.get("object") == "page":
            handle_messenger_webhook(channel, payload)
        return HttpResponse("EVENT_RECEIVED")

    return HttpResponse("Method not allowed", status=405)


# ── WebChat Widget API ─────────────────────────────────────────────────────────

@csrf_exempt
def webchat_init(request, widget_key: str):
    """Visitor khởi tạo session chat."""
    try:
        channel = ChannelConfig.objects.get(
            webchat_widget_key=widget_key,
            channel_type="WEBCHAT",
            status="ACTIVE",
        )
    except ChannelConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid widget key"}, status=404)

    # Kiểm tra origin
    origin = request.headers.get("Origin", "")
    allowed = [o.strip() for o in channel.webchat_allowed_origins.splitlines() if o.strip()]
    if allowed and not any(origin.startswith(a) for a in allowed):
        return JsonResponse({"error": "Origin not allowed"}, status=403)

    # Tạo session_id ngẫu nhiên
    session_id = str(uuid_lib.uuid4()).replace("-", "")[:20]

    return JsonResponse({
        "session_id":       session_id,
        "greeting":         channel.webchat_greeting,
        "offline_message":  channel.webchat_offline_message,
        "theme_color":      channel.webchat_theme_color,
        "channel_name":     channel.name,
        "channel_avatar":   channel.avatar_url,
    })


@csrf_exempt
def webchat_send(request, widget_key: str):
    """Visitor gửi tin nhắn."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        channel = ChannelConfig.objects.get(
            webchat_widget_key=widget_key,
            channel_type="WEBCHAT",
            status="ACTIVE",
        )
    except ChannelConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid"}, status=404)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Bad JSON"}, status=400)

    session_id   = body.get("session_id", "")
    text         = (body.get("text") or "").strip()
    visitor_name = (body.get("name") or "").strip()

    if not session_id or not text:
        return JsonResponse({"error": "session_id and text required"}, status=400)

    from apps.engagement.services.channel_service import handle_webchat_message
    msg = handle_webchat_message(channel, session_id, text, visitor_name)

    return JsonResponse({
        "ok":      True,
        "msg_id":  msg.id,
        "sent_at": msg.sent_at.isoformat(),
    })


@csrf_exempt
@require_GET
def webchat_poll(request, widget_key: str):
    """Visitor poll tin nhắn mới từ agent (long-poll fallback)."""
    try:
        channel = ChannelConfig.objects.get(
            webchat_widget_key=widget_key,
            channel_type="WEBCHAT",
            status="ACTIVE",
        )
    except ChannelConfig.DoesNotExist:
        return JsonResponse({"error": "Invalid"}, status=404)

    session_id = request.GET.get("session_id", "")
    after_id   = int(request.GET.get("after_id", 0))

    from apps.engagement.models import Conversation, Message
    conv = Conversation.objects.filter(channel=channel, external_id=session_id).first()
    if not conv:
        return JsonResponse({"messages": []})

    msgs = Message.objects.filter(
        conversation=conv,
        id__gt=after_id,
    ).values("id", "direction", "content", "msg_type", "sent_at")

    # Mark OUT messages as read
    Message.objects.filter(conversation=conv, direction="OUT", is_read=False).update(is_read=True)

    return JsonResponse({
        "messages": [
            {
                "id":        m["id"],
                "direction": m["direction"],
                "content":   m["content"],
                "type":      m["msg_type"],
                "sent_at":   m["sent_at"].isoformat(),
            }
            for m in msgs
        ]
    })
