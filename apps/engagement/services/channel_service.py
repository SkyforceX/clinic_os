"""
engagement/services/channel_service.py
==================================
Xử lý webhook đến từ Zalo OA / Facebook Messenger / WebChat
và gửi tin nhắn ra ngoài qua các platform API.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger("engagement.channel")


# ── Conversation / Message helpers ────────────────────────────────────────────

def _get_or_create_conversation(channel, external_id: str, customer_name: str = "", avatar: str = "") -> "Conversation":
    from apps.engagement.models import Conversation
    conv, created = Conversation.objects.get_or_create(
        channel=channel,
        external_id=external_id,
        defaults={
            "customer_name":   customer_name,
            "customer_avatar": avatar,
            "status":          Conversation.Status.OPEN,
            "last_message_at": timezone.now(),
        },
    )
    if not created and customer_name and not conv.customer_name:
        conv.customer_name = customer_name
        conv.save(update_fields=["customer_name"])
    return conv


def _save_inbound_message(conversation, content: str, msg_type: str = "TEXT",
                           attachments=None, external_msg_id: str = "") -> "Message":
    from apps.engagement.models import Message
    msg = Message.objects.create(
        conversation=conversation,
        direction=Message.Direction.IN,
        msg_type=msg_type,
        content=content,
        attachments=attachments or [],
        external_msg_id=external_msg_id,
    )
    conversation.last_message_at = timezone.now()
    conversation.status = Conversation.Status.OPEN
    conversation.save(update_fields=["last_message_at", "status"])

    # Auto-reply nếu bật
    if conversation.channel.auto_reply_enabled and not conversation.first_reply_at:
        _send_auto_reply(conversation)

    return msg


# ── Zalo OA ──────────────────────────────────────────────────────────────────

def verify_zalo_webhook(channel, request) -> bool:
    """Xác thực chữ ký Zalo webhook."""
    mac_str = request.headers.get("X-ZEvent-Signature", "")
    if not channel.zalo_secret_key or not mac_str:
        return True  # không có key → skip verify
    body = request.body
    expected = hmac.new(
        channel.zalo_secret_key.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, mac_str)


def handle_zalo_webhook(channel, payload: dict) -> bool:
    """Xử lý payload webhook Zalo OA."""
    try:
        event_name = payload.get("event_name", "")
        sender     = payload.get("sender", {})
        message    = payload.get("message", {})

        if event_name not in ("user_send_text", "user_send_image", "user_send_file", "user_send_sticker"):
            return True  # ignore non-message events

        external_id   = sender.get("id", "")
        display_name  = sender.get("display_name", "")
        avatar        = sender.get("avatar", "")
        content       = message.get("text", "")
        msg_id        = message.get("msg_id", "")

        msg_type_map = {
            "user_send_text":    "TEXT",
            "user_send_image":   "IMAGE",
            "user_send_file":    "FILE",
            "user_send_sticker": "STICKER",
        }
        msg_type = msg_type_map.get(event_name, "TEXT")

        attachments = []
        if "attachments" in message:
            for att in message["attachments"]:
                attachments.append({
                    "type": att.get("type"),
                    "payload": att.get("payload", {}),
                })

        conv = _get_or_create_conversation(channel, external_id, display_name, avatar)
        _save_inbound_message(conv, content, msg_type, attachments, msg_id)
        return True
    except Exception as exc:
        logger.error(f"Zalo webhook error: {exc}", exc_info=True)
        return False


def send_zalo_message(channel, external_id: str, text: str, attachments=None) -> bool:
    """Gửi tin nhắn đến user qua Zalo OA API."""
    try:
        import urllib.request as urlreq
        payload = {
            "recipient": {"user_id": external_id},
            "message":   {"text": text},
        }
        if attachments:
            payload["message"]["attachments"] = attachments

        data    = json.dumps(payload).encode()
        req     = urlreq.Request(
            "https://openapi.zalo.me/v3.0/oa/message/cs",
            data=data,
            headers={
                "Content-Type":  "application/json",
                "access_token":  channel.zalo_access_token,
            },
            method="POST",
        )
        with urlreq.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("error") == 0
    except Exception as exc:
        logger.error(f"Zalo send error: {exc}", exc_info=True)
        return False


# ── Facebook Messenger ────────────────────────────────────────────────────────

def verify_fb_webhook(channel, request) -> bool:
    """Xác thực X-Hub-Signature-256."""
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not channel.fb_app_secret or not sig:
        return True
    expected = "sha256=" + hmac.new(
        channel.fb_app_secret.encode(),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def handle_messenger_webhook(channel, payload: dict) -> bool:
    """Xử lý payload webhook Facebook Messenger."""
    try:
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id", "")
                msg_data  = event.get("message", {})
                if not msg_data or msg_data.get("is_echo"):
                    continue

                text        = msg_data.get("text", "")
                msg_id      = msg_data.get("mid", "")
                attachments = []
                msg_type    = "TEXT"

                for att in msg_data.get("attachments", []):
                    t = att.get("type", "")
                    type_map = {"image":"IMAGE","video":"VIDEO","audio":"AUDIO","file":"FILE"}
                    msg_type = type_map.get(t, "TEXT")
                    attachments.append({"type": t, "url": att.get("payload", {}).get("url", "")})

                conv = _get_or_create_conversation(channel, sender_id)
                _save_inbound_message(conv, text, msg_type, attachments, msg_id)
        return True
    except Exception as exc:
        logger.error(f"Messenger webhook error: {exc}", exc_info=True)
        return False


def send_messenger_message(channel, external_id: str, text: str) -> bool:
    """Gửi tin nhắn qua Graph API."""
    try:
        import urllib.request as urlreq
        payload = {
            "recipient": {"id": external_id},
            "message":   {"text": text},
        }
        url  = f"https://graph.facebook.com/v18.0/me/messages?access_token={channel.fb_page_access_token}"
        data = json.dumps(payload).encode()
        req  = urlreq.Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST")
        with urlreq.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return "error" not in result
    except Exception as exc:
        logger.error(f"Messenger send error: {exc}", exc_info=True)
        return False


# ── WebChat ───────────────────────────────────────────────────────────────────

def handle_webchat_message(channel, session_id: str, text: str, visitor_name: str = "") -> "Message":
    """Lưu tin nhắn từ widget website."""
    conv = _get_or_create_conversation(channel, session_id, visitor_name or f"Khách {session_id[:8]}")
    return _save_inbound_message(conv, text, "TEXT")


# ── Send reply (dispatch theo channel type) ────────────────────────────────────

def send_reply(conversation, text: str, agent=None, is_internal: bool = False) -> "Message":
    """Gửi phản hồi và lưu vào DB."""
    from apps.engagement.models import Message

    msg = Message.objects.create(
        conversation=conversation,
        direction=Message.Direction.OUT,
        msg_type=Message.MessageType.TEXT,
        content=text,
        sender_agent=agent,
        is_internal=is_internal,
    )

    conversation.last_message_at = timezone.now()
    if not conversation.first_reply_at and not is_internal:
        conversation.first_reply_at = timezone.now()
    conversation.save(update_fields=["last_message_at","first_reply_at"])

    if is_internal:
        return msg

    ch   = conversation.channel
    xid  = conversation.external_id
    ctype = ch.channel_type

    try:
        if ctype == "ZALO":
            send_zalo_message(ch, xid, text)
        elif ctype == "MESSENGER":
            send_messenger_message(ch, xid, text)
        # WEBCHAT: client polls /engagement/api/webchat/messages/ → no push needed
    except Exception as exc:
        logger.error(f"send_reply dispatch error [{ctype}]: {exc}")

    return msg


# ── Auto-reply ────────────────────────────────────────────────────────────────

def _send_auto_reply(conversation) -> None:
    ch = conversation.channel
    if ch.auto_reply_text:
        send_reply(conversation, ch.auto_reply_text, agent=None)
