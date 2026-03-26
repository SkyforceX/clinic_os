'''
mỗi lần phát hành tài liệu là lưu snapshot
biết đang dùng template nào
biết file nào là bản chính thức
version hóa
'''

from django.conf import settings
from django.db import models

from apps.contract.models.quotation import QuotationDraft


class DocumentTemplate(models.Model):
    DOC_TYPE_QUOTATION = "QUOTATION"
    DOC_TYPE_CONTRACT = "CONTRACT"

    DOC_TYPE_CHOICES = (
        (DOC_TYPE_QUOTATION, "Quotation"),
        (DOC_TYPE_CONTRACT, "Contract"),
    )

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    version = models.CharField(max_length=50, default="v1")
    is_active = models.BooleanField(default=True)

    # Có thể để trống để dùng built-in default DOCX generator
    docx_file = models.FileField(
        upload_to="contract/templates/",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_document_template"
        ordering = ["doc_type", "-is_active", "-updated_at", "-id"]

    def __str__(self):
        return f"{self.doc_type} - {self.code} - {self.version}"


class IssuedDocument(models.Model):
    DOC_TYPE_QUOTATION = "QUOTATION"
    DOC_TYPE_CONTRACT = "CONTRACT"

    DOC_TYPE_CHOICES = (
        (DOC_TYPE_QUOTATION, "Quotation"),
        (DOC_TYPE_CONTRACT, "Contract"),
    )

    STATUS_DRAFT = "DRAFT"
    STATUS_ISSUED = "ISSUED"
    STATUS_SUPERSEDED = "SUPERSEDED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_ISSUED, "Issued"),
        (STATUS_SUPERSEDED, "Superseded"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    quotation = models.ForeignKey(
        QuotationDraft,
        on_delete=models.CASCADE,
        related_name="issued_documents",
        null=True,
        blank=True,
    )

    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.PROTECT,
        related_name="issued_documents",
        null=True,
        blank=True,
    )

    version = models.PositiveIntegerField(default=1)
    payload_json = models.JSONField(default=dict, blank=True)

    docx_file = models.FileField(
        upload_to="contract/issued/docx/",
        null=True,
        blank=True,
    )
    pdf_file = models.FileField(
        upload_to="contract/issued/pdf/",
        null=True,
        blank=True,
    )

    issued_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_contract_documents",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_issued_document"
        ordering = ["-issued_at", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["doc_type", "status"]),
            models.Index(fields=["quotation", "doc_type"]),
        ]

    def __str__(self):
        target = ""
        if self.quotation_id:
            target = f"quotation:{self.quotation_id}"
        return f"{self.doc_type} v{self.version} - {target}".strip()