"""
engagement/models/channel.py
========================
Cấu hình tích hợp kênh chat (Zalo OA, Facebook Messenger, Website Widget)
và quản lý hội thoại đa kênh.
"""
import uuid

from django.conf import settings
from django.db import models


# ── Channel Integration Config ────────────────────────────────────────────────

class ChannelConfig(models.Model):
    """
    Cấu hình tích hợp cho một kênh chat.
    Mỗi kênh (Zalo OA, Page Facebook, Website) tạo một bản ghi.
    """

    class ChannelType(models.TextChoices):
        ZALO      = "ZALO",      "Zalo Official Account"
        MESSENGER = "MESSENGER", "Facebook Messenger"
        WEBCHAT   = "WEBCHAT",   "Website Chat Widget"
        EMAIL     = "EMAIL",     "Email"

    class Status(models.TextChoices):
        ACTIVE   = "ACTIVE",   "Hoạt động"
        INACTIVE = "INACTIVE", "Tắt"
        ERROR    = "ERROR",    "Lỗi kết nối"

    name         = models.CharField(max_length=100, verbose_name="Tên kênh")
    channel_type = models.CharField(max_length=12, choices=ChannelType.choices, db_index=True)
    status       = models.CharField(max_length=10, choices=Status.choices, default=Status.INACTIVE)
    avatar_url   = models.URLField(blank=True, verbose_name="Avatar kênh")
    description  = models.CharField(max_length=255, blank=True)

    # ── Zalo OA ───────────────────────────────────────────────────────────────
    zalo_oa_id        = models.CharField(max_length=100, blank=True, verbose_name="Zalo OA ID")
    zalo_access_token = models.TextField(blank=True, verbose_name="Zalo Access Token")
    zalo_refresh_token= models.TextField(blank=True, verbose_name="Zalo Refresh Token")
    zalo_secret_key   = models.CharField(max_length=255, blank=True, verbose_name="Zalo Secret Key")
    zalo_webhook_token= models.CharField(max_length=255, blank=True, verbose_name="Zalo Webhook Token")

    # ── Facebook Messenger ────────────────────────────────────────────────────
    fb_page_id        = models.CharField(max_length=100, blank=True, verbose_name="Facebook Page ID")
    fb_page_access_token = models.TextField(blank=True, verbose_name="Page Access Token")
    fb_app_secret     = models.CharField(max_length=255, blank=True, verbose_name="App Secret")
    fb_verify_token   = models.CharField(max_length=255, blank=True, verbose_name="Webhook Verify Token")
    fb_app_id         = models.CharField(max_length=100, blank=True, verbose_name="Facebook App ID")

    # ── Website Chat Widget ────────────────────────────────────────────────────
    webchat_widget_key     = models.UUIDField(default=uuid.uuid4, unique=True)
    webchat_allowed_origins = models.TextField(
        blank=True,
        verbose_name="Allowed Origins (mỗi domain 1 dòng)",
        help_text="VD: https://vietmedi.vn",
    )
    webchat_greeting        = models.CharField(max_length=255, blank=True, default="Xin chào! Chúng tôi có thể giúp gì cho bạn?")
    webchat_offline_message = models.CharField(max_length=255, blank=True, default="Hiện tại chúng tôi đang offline. Chúng tôi sẽ phản hồi sớm nhất!")
    webchat_theme_color     = models.CharField(max_length=7, default="#1a5276", verbose_name="Màu theme widget")
    webchat_position        = models.CharField(
        max_length=12, default="bottom-right",
        choices=[("bottom-right","Dưới phải"), ("bottom-left","Dưới trái")],
    )

    # ── Email ─────────────────────────────────────────────────────────────────
    email_address    = models.EmailField(blank=True)
    email_imap_host  = models.CharField(max_length=100, blank=True)
    email_imap_port  = models.PositiveIntegerField(default=993)
    email_smtp_host  = models.CharField(max_length=100, blank=True)
    email_smtp_port  = models.PositiveIntegerField(default=587)
    email_username   = models.CharField(max_length=100, blank=True)
    email_password   = models.TextField(blank=True)
    email_use_tls    = models.BooleanField(default=True)

    # ── Auto-reply ─────────────────────────────────────────────────────────────
    auto_reply_enabled = models.BooleanField(default=False, verbose_name="Bật tự động phản hồi")
    auto_reply_text    = models.TextField(blank=True, verbose_name="Nội dung tự động phản hồi")
    business_hours_start = models.TimeField(null=True, blank=True, verbose_name="Giờ bắt đầu làm việc")
    business_hours_end   = models.TimeField(null=True, blank=True, verbose_name="Giờ kết thúc làm việc")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = "care_channel_config"
        ordering     = ["channel_type", "name"]
        verbose_name = "Kênh tích hợp"

    def __str__(self):
        return f"{self.get_channel_type_display()} – {self.name}"

    @property
    def webhook_url_path(self) -> str:
        """Path để cấu hình trên platform."""
        type_slug = self.channel_type.lower()
        return f"/engagement/webhook/{type_slug}/{self.pk}/"

    @property
    def embed_script(self) -> str:
        if self.channel_type != self.ChannelType.WEBCHAT:
            return ""
        return (
            f'<script src="https://yourdomain.com/static/engagement/js/widget.js" '
            f'data-key="{self.webchat_widget_key}" async></script>'
        )


# ── Conversation ───────────────────────────────────────────────────────────────

class Conversation(models.Model):
    """Một chuỗi hội thoại với khách hàng qua một kênh."""

    class Status(models.TextChoices):
        OPEN       = "OPEN",       "Đang mở"
        PENDING    = "PENDING",    "Chờ phản hồi"
        RESOLVED   = "RESOLVED",   "Đã giải quyết"
        SNOOZED    = "SNOOZED",    "Tạm ẩn"

    class Priority(models.TextChoices):
        LOW    = "LOW",    "Thấp"
        MEDIUM = "MEDIUM", "Trung bình"
        HIGH   = "HIGH",   "Cao"
        URGENT = "URGENT", "Khẩn cấp"

    uuid         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    channel      = models.ForeignKey(ChannelConfig, on_delete=models.CASCADE, related_name="conversations")
    status       = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    priority     = models.CharField(max_length=8, choices=Priority.choices, default=Priority.MEDIUM)

    # ── Thông tin khách hàng (từ platform)
    external_id       = models.CharField(max_length=255, db_index=True, verbose_name="ID người dùng trên platform")
    customer_name     = models.CharField(max_length=255, blank=True, verbose_name="Tên khách hàng")
    customer_avatar   = models.URLField(blank=True)
    customer_platform_data = models.JSONField(default=dict, blank=True)

    # ── Liên kết nội bộ
    assigned_to  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="engagement_conversations",
        verbose_name="Agent phụ trách",
    )
    linked_contact = models.ForeignKey(
        "engagement.Contact", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="conversations",
        verbose_name="Liên kết contact",
    )
    linked_company = models.ForeignKey(
        "organizations.Company", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="engagement_conversations",
    )

    # ── Tags & metadata
    tags     = models.ManyToManyField("engagement.ConversationTag", blank=True, related_name="conversations")
    subject  = models.CharField(max_length=255, blank=True, verbose_name="Chủ đề")
    internal_note = models.TextField(blank=True, verbose_name="Ghi chú nội bộ")

    # ── Timestamps
    first_reply_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian phản hồi đầu tiên")
    resolved_at    = models.DateTimeField(null=True, blank=True)
    snoozed_until  = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # ── CSAT
    csat_score   = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="CSAT (1-5)")
    csat_comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table   = "care_conversation"
        ordering   = ["-last_message_at", "-created_at"]
        verbose_name = "Hội thoại"
        indexes    = [
            models.Index(fields=["channel", "external_id"]),
            models.Index(fields=["status", "assigned_to"]),
        ]

    def __str__(self):
        return f"{self.customer_name or self.external_id} [{self.channel}]"

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    @property
    def unread_count(self):
        return self.messages.filter(direction="IN", is_read=False).count()


# ── Message ────────────────────────────────────────────────────────────────────

class Message(models.Model):
    """Một tin nhắn trong hội thoại."""

    class Direction(models.TextChoices):
        IN  = "IN",  "Đến (từ khách)"
        OUT = "OUT", "Đi (từ agent)"

    class MessageType(models.TextChoices):
        TEXT     = "TEXT",     "Văn bản"
        IMAGE    = "IMAGE",    "Hình ảnh"
        FILE     = "FILE",     "File"
        STICKER  = "STICKER",  "Sticker"
        AUDIO    = "AUDIO",    "Audio"
        VIDEO    = "VIDEO",    "Video"
        TEMPLATE = "TEMPLATE", "Template"
        EVENT    = "EVENT",    "Sự kiện hệ thống"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    direction    = models.CharField(max_length=3, choices=Direction.choices, db_index=True)
    msg_type     = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    content      = models.TextField(blank=True)
    attachments  = models.JSONField(default=list, blank=True)
    external_msg_id = models.CharField(max_length=255, blank=True, db_index=True)

    sender_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="engagement_messages_sent",
    )

    is_read    = models.BooleanField(default=False, db_index=True)
    is_internal = models.BooleanField(default=False, verbose_name="Ghi chú nội bộ (không gửi KH)")
    sent_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "engagement_message"
        ordering = ["sent_at"]
        verbose_name = "Tin nhắn"

    def __str__(self):
        return f"[{self.direction}] {self.content[:60]}"


# ── Tags ──────────────────────────────────────────────────────────────────────

class ConversationTag(models.Model):
    name  = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6c757d")

    class Meta:
        db_table = "engagement_conversation_tag"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ── Quick Replies (Canned Responses) ──────────────────────────────────────────

class CannedResponse(models.Model):
    """Mẫu phản hồi nhanh để agent dùng lại."""
    title    = models.CharField(max_length=100, verbose_name="Tiêu đề")
    shortcut = models.CharField(max_length=30, unique=True, verbose_name="Phím tắt (/...)")
    content  = models.TextField(verbose_name="Nội dung")
    channel_types = models.JSONField(default=list, blank=True, verbose_name="Kênh áp dụng")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "engagement_canned_response"
        ordering = ["title"]
        verbose_name = "Mẫu phản hồi nhanh"

    def __str__(self):
        return f"/{self.shortcut} – {self.title}"
