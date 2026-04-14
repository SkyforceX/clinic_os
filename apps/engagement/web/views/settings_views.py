import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.engagement.models import CannedResponse, ChannelConfig, ConversationTag
from apps.engagement.policies import EngagementPolicy
from apps.engagement.selectors.conversation_selectors import get_care_stats


def _deny(request):
    if not EngagementPolicy.can_manage_channels(request.user):
        return HttpResponseForbidden("<h2>403 – Chỉ Engagement Admin mới truy cập phần này.</h2>")
    return None


@login_required(login_url="authentication:staff_login")
def settings_overview(request):
    denied = _deny(request)
    if denied:
        return denied

    channels = ChannelConfig.objects.all().order_by("channel_type","name")
    canned   = CannedResponse.objects.all()
    tags     = ConversationTag.objects.all()
    stats    = get_care_stats(days=30)

    return render(request, "engagement/staff/settings.html", {
        "channels":      channels,
        "canned":        canned,
        "tags":          tags,
        "stats":         stats,
        "channel_types": ChannelConfig.ChannelType.choices,
    })


@login_required(login_url="authentication:staff_login")
def channel_form(request, channel_id=None):
    denied = _deny(request)
    if denied:
        return denied

    channel = get_object_or_404(ChannelConfig, pk=channel_id) if channel_id else None

    if request.method == "POST":
        p = request.POST
        data = {
            "name":                 p.get("name","").strip(),
            "channel_type":         p.get("channel_type","WEBCHAT"),
            "description":          p.get("description",""),
            "avatar_url":           p.get("avatar_url",""),
            "status":               p.get("status","INACTIVE"),
            # Zalo
            "zalo_oa_id":           p.get("zalo_oa_id",""),
            "zalo_access_token":    p.get("zalo_access_token",""),
            "zalo_refresh_token":   p.get("zalo_refresh_token",""),
            "zalo_secret_key":      p.get("zalo_secret_key",""),
            "zalo_webhook_token":   p.get("zalo_webhook_token",""),
            # Messenger
            "fb_page_id":           p.get("fb_page_id",""),
            "fb_page_access_token": p.get("fb_page_access_token",""),
            "fb_app_secret":        p.get("fb_app_secret",""),
            "fb_verify_token":      p.get("fb_verify_token",""),
            "fb_app_id":            p.get("fb_app_id",""),
            # WebChat
            "webchat_allowed_origins":  p.get("webchat_allowed_origins",""),
            "webchat_greeting":         p.get("webchat_greeting",""),
            "webchat_offline_message":  p.get("webchat_offline_message",""),
            "webchat_theme_color":      p.get("webchat_theme_color","#1a5276"),
            "webchat_position":         p.get("webchat_position","bottom-right"),
            # Auto-reply
            "auto_reply_enabled":   p.get("auto_reply_enabled") == "on",
            "auto_reply_text":      p.get("auto_reply_text",""),
            # Email
            "email_address":        p.get("email_address",""),
            "email_imap_host":      p.get("email_imap_host",""),
            "email_smtp_host":      p.get("email_smtp_host",""),
            "email_username":       p.get("email_username",""),
            "email_use_tls":        p.get("email_use_tls") == "on",
        }
        if p.get("email_password","").strip():
            data["email_password"] = p.get("email_password","")
        if p.get("email_imap_port","").isdigit():
            data["email_imap_port"] = int(p["email_imap_port"])
        if p.get("email_smtp_port","").isdigit():
            data["email_smtp_port"] = int(p["email_smtp_port"])

        if not data["name"]:
            messages.error(request, "Vui lòng nhập tên kênh.")
        else:
            if channel:
                for k, v in data.items():
                    setattr(channel, k, v)
                channel.save()
                messages.success(request, f"Đã cập nhật kênh '{channel.name}'.")
            else:
                channel = ChannelConfig.objects.create(**data, created_by=request.user)
                messages.success(request, f"Đã tạo kênh '{channel.name}'.")
            return redirect("engagement:settings")

    return render(request, "engagement/staff/channel_form.html", {
        "channel": channel,
        "channel_types": ChannelConfig.ChannelType.choices,
    })


@login_required(login_url="authentication:staff_login")
@require_POST
def channel_delete(request, channel_id):
    denied = _deny(request)
    if denied:
        return denied
    ch = get_object_or_404(ChannelConfig, pk=channel_id)
    ch.delete()
    messages.success(request, "Đã xóa kênh.")
    return redirect("engagement:settings")


@login_required(login_url="authentication:staff_login")
@require_POST
def canned_save(request):
    denied = _deny(request)
    if denied:
        return denied
    body = json.loads(request.body)
    cid  = body.get("id")
    if cid:
        obj = get_object_or_404(CannedResponse, pk=cid)
        obj.title    = body.get("title","")
        obj.shortcut = body.get("shortcut","")
        obj.content  = body.get("content","")
        obj.save()
    else:
        obj = CannedResponse.objects.create(
            title=body.get("title",""),
            shortcut=body.get("shortcut",""),
            content=body.get("content",""),
            created_by=request.user,
        )
    return JsonResponse({"ok": True, "id": obj.id})


@login_required(login_url="authentication:staff_login")
@require_POST
def canned_delete(request, canned_id):
    denied = _deny(request)
    if denied:
        return denied
    get_object_or_404(CannedResponse, pk=canned_id).delete()
    return JsonResponse({"ok": True})
