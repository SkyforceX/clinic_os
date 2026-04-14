"""
approvals/models/approval_attachment.py
=========================================
File đính kèm riêng tư cho yêu cầu phê duyệt.
Không nằm trong thư viện media công khai.
Truy cập thông qua view có kiểm tra quyền.
"""

from django.conf import settings
from django.db import models


class ApprovalAttachment(models.Model):
    approval_request = models.ForeignKey(
        "approvals.ApprovalRequest",
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Yêu cầu phê duyệt",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        verbose_name="Người tải lên",
    )
    file = models.FileField(
        upload_to="approvals/private/%Y/%m/",
        verbose_name="Tệp",
    )
    filename    = models.CharField(max_length=255, verbose_name="Tên tệp")
    file_size   = models.PositiveIntegerField(default=0, verbose_name="Kích thước (bytes)")
    content_type = models.CharField(max_length=120, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approvals_attachment"
        ordering = ["created_at"]
        verbose_name = "Tệp đính kèm phê duyệt"

    def __str__(self):
        return self.filename

    @property
    def size_display(self) -> str:
        b = self.file_size
        if b < 1024:
            return f"{b} B"
        if b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b / 1024 / 1024:.1f} MB"

    @property
    def is_image(self) -> bool:
        return self.content_type.startswith("image/")

    @property
    def is_pdf(self) -> bool:
        return self.content_type == "application/pdf"

    @property
    def icon_class(self) -> str:
        ct = self.content_type
        if ct.startswith("image/"):
            return "fa-file-image"
        if ct == "application/pdf":
            return "fa-file-pdf"
        if "word" in ct or "document" in ct:
            return "fa-file-word"
        if "excel" in ct or "spreadsheet" in ct:
            return "fa-file-excel"
        if "zip" in ct or "compressed" in ct:
            return "fa-file-archive"
        return "fa-file-alt"
