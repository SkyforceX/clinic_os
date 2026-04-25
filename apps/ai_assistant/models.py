from django.db import models
from django.conf import settings


class KnowledgeDocumentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class KnowledgeDocumentManager(models.Manager):
    def get_queryset(self):
        return KnowledgeDocumentQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()


class KnowledgeChunkQuerySet(models.QuerySet):
    def with_embeddings(self):
        return self.exclude(embedding=[])


class KnowledgeChunkManager(models.Manager):
    def get_queryset(self):
        return KnowledgeChunkQuerySet(self.model, using=self._db)

    def with_embeddings(self):
        return self.get_queryset().with_embeddings()


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


class KnowledgeDocument(models.Model):
    SOURCE_PROCEDURE = "procedure"
    SOURCE_CATEGORY = "checkup_category"
    SOURCE_PACKAGE = "checkup_package"
    SOURCE_CHOICES = [
        (SOURCE_PROCEDURE, "Quy trình"),
        (SOURCE_CATEGORY, "Danh mục khám"),
        (SOURCE_PACKAGE, "Gói khám mẫu"),
    ]

    source_type = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    source_id = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    last_indexed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    records = KnowledgeDocumentManager()

    class Meta:
        app_label = "ai_assistant"
        ordering = ["source_type", "source_id"]
        verbose_name = "Tài liệu tri thức AI"
        verbose_name_plural = "Tài liệu tri thức AI"
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id"],
                name="uq_ai_knowledge_source",
            )
        ]

    def __str__(self):
        return f"{self.get_source_type_display()}: {self.title}"


class KnowledgeChunk(models.Model):
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64)
    embedding = models.JSONField(default=list, blank=True)
    char_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    records = KnowledgeChunkManager()

    class Meta:
        app_label = "ai_assistant"
        ordering = ["document_id", "chunk_index"]
        verbose_name = "Đoạn tri thức AI"
        verbose_name_plural = "Đoạn tri thức AI"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="uq_ai_knowledge_chunk_per_doc",
            )
        ]

    def __str__(self):
        return f"{self.document_id}#{self.chunk_index}"
