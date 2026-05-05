from __future__ import annotations

from django.conf import settings
from django.db import models

from .fields import VectorField


DEFAULT_EMBEDDING_DIMENSIONS = int(
    getattr(settings, "AI_EMBED_DIMENSIONS", 768)
)


class AIKnowledgeSource(models.Model):
    STATUS_PENDING = "pending"
    STATUS_INDEXED = "indexed"
    STATUS_STALE = "stale"
    STATUS_FAILED = "failed"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_STALE, "Stale"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DISABLED, "Disabled"),
    ]

    ACCESS_PUBLIC = "public"
    ACCESS_INTERNAL = "internal"
    ACCESS_MANAGER = "manager"
    ACCESS_CONTRACT = "contract"
    ACCESS_CLINICAL = "clinical"
    ACCESS_PATIENT = "patient"
    ACCESS_ADMIN = "admin"
    ACCESS_CHOICES = [
        (ACCESS_PUBLIC, "Public"),
        (ACCESS_INTERNAL, "Internal"),
        (ACCESS_MANAGER, "Manager"),
        (ACCESS_CONTRACT, "Contract"),
        (ACCESS_CLINICAL, "Clinical"),
        (ACCESS_PATIENT, "Patient"),
        (ACCESS_ADMIN, "Admin"),
    ]

    SOURCE_PROCEDURE = "procedure"
    SOURCE_CATEGORY = "checkup_category"
    SOURCE_PACKAGE = "checkup_package"
    SOURCE_PAGE = "page"
    SOURCE_POST = "post"
    SOURCE_FAQ = "faq"
    SOURCE_SERVICE = "service"
    SOURCE_CONTRACT = "contract"
    SOURCE_QUOTATION = "quotation"
    SOURCE_POLICY = "policy"
    SOURCE_PATIENT_SUMMARY = "patient_summary"
    SOURCE_VISIT_SUMMARY = "visit_summary"
    SOURCE_CLINICAL_NOTE = "clinical_note"
    SOURCE_MEDICAL_RECORD = "medical_record"
    SOURCE_DOCUMENT = "document"
    SOURCE_INTERNAL_NOTE = "internal_note"
    SOURCE_CHOICES = [
        (SOURCE_PROCEDURE, "Procedure"),
        (SOURCE_CATEGORY, "Checkup Category"),
        (SOURCE_PACKAGE, "Checkup Package"),
        (SOURCE_PAGE, "Page"),
        (SOURCE_POST, "Post"),
        (SOURCE_FAQ, "FAQ"),
        (SOURCE_SERVICE, "Service"),
        (SOURCE_CONTRACT, "Contract"),
        (SOURCE_QUOTATION, "Quotation"),
        (SOURCE_POLICY, "Policy"),
        (SOURCE_PATIENT_SUMMARY, "Patient Summary"),
        (SOURCE_VISIT_SUMMARY, "Visit Summary"),
        (SOURCE_CLINICAL_NOTE, "Clinical Note"),
        (SOURCE_MEDICAL_RECORD, "Medical Record"),
        (SOURCE_DOCUMENT, "Document"),
        (SOURCE_INTERNAL_NOTE, "Internal Note"),
    ]

    source_type = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    source_id = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    source_url = models.CharField(max_length=500, blank=True)
    locale = models.CharField(max_length=16, default="vi")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    content_hash = models.CharField(max_length=64, blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    access_level = models.CharField(
        max_length=16,
        choices=ACCESS_CHOICES,
        default=ACCESS_INTERNAL,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_type", "source_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id"],
                name="uq_ai_knowledge_source_type_id",
            )
        ]
        indexes = [
            models.Index(fields=["source_type"], name="ai_kn_src_type_idx"),
            models.Index(fields=["status"], name="ai_kn_src_status_idx"),
            models.Index(fields=["access_level"], name="ai_kn_src_access_idx"),
            models.Index(fields=["locale"], name="ai_kn_src_locale_idx"),
        ]

    def __str__(self):
        return f"{self.source_type}:{self.source_id} {self.title}"


class AIKnowledgeChunk(models.Model):
    source_record = models.ForeignKey(
        AIKnowledgeSource,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    source_type = models.CharField(max_length=32)
    source_id = models.CharField(max_length=64)
    section_key = models.CharField(max_length=128, blank=True)
    chunk_index = models.PositiveIntegerField()
    title = models.CharField(max_length=255, blank=True)
    section_title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    embedding = VectorField(
        dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
        null=True,
        blank=True,
    )
    embedding_model = models.CharField(max_length=128, blank=True)
    embedding_dim = models.PositiveIntegerField(default=DEFAULT_EMBEDDING_DIMENSIONS)
    token_count = models.PositiveIntegerField(default=0)
    prev_chunk_index = models.PositiveIntegerField(null=True, blank=True)
    next_chunk_index = models.PositiveIntegerField(null=True, blank=True)
    access_level = models.CharField(
        max_length=16,
        choices=AIKnowledgeSource.ACCESS_CHOICES,
        default=AIKnowledgeSource.ACCESS_INTERNAL,
    )
    locale = models.CharField(max_length=16, default="vi")
    status = models.CharField(
        max_length=16,
        choices=AIKnowledgeSource.STATUS_CHOICES,
        default=AIKnowledgeSource.STATUS_INDEXED,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_id", "section_key", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_record", "chunk_index"],
                name="uq_ai_knowledge_chunk_source_idx",
            )
        ]
        indexes = [
            models.Index(fields=["source_type"], name="ai_kn_chunk_type_idx"),
            models.Index(fields=["source_id"], name="ai_kn_chunk_srcid_idx"),
            models.Index(fields=["access_level"], name="ai_kn_chunk_access_idx"),
            models.Index(fields=["locale"], name="ai_kn_chunk_locale_idx"),
            models.Index(fields=["status"], name="ai_kn_chunk_status_idx"),
            models.Index(fields=["section_key"], name="ai_kn_chunk_section_idx"),
            models.Index(fields=["chunk_index"], name="ai_kn_chunk_order_idx"),
            models.Index(
                fields=["source_id", "section_key", "chunk_index"],
                name="ai_kn_chunk_scope_idx",
            ),
        ]

    def __str__(self):
        return f"{self.source_type}:{self.source_id}#{self.chunk_index}"
