from django.db import models
from django.conf import settings


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
        verbose_name="Người dùng",
    )
    title = models.CharField(max_length=255, blank=True, verbose_name="Tiêu đề")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai_assistant"
        ordering = ["-updated_at"]
        verbose_name = "Cuộc hội thoại"
        verbose_name_plural = "Lịch sử hội thoại"

    def __str__(self):
        return self.title or f"Hội thoại #{self.pk}"

    def get_title_display(self):
        return self.title or f"Hội thoại #{self.pk}"


class Message(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_CHOICES = [
        (ROLE_USER, "Người dùng"),
        (ROLE_ASSISTANT, "Trợ lý"),
        (ROLE_SYSTEM, "Hệ thống"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Hội thoại",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, verbose_name="Vai trò")
    content = models.TextField(verbose_name="Nội dung")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai_assistant"
        ordering = ["created_at"]
        verbose_name = "Tin nhắn"
        verbose_name_plural = "Tin nhắn"

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"
