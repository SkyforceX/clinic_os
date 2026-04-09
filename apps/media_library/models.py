from __future__ import annotations

import os

from django.conf import settings
from django.db import models
from django.utils import timezone


def _upload_path(instance: "MediaFile", filename: str) -> str:
    today = timezone.now()
    return f"media_library/{today.year}/{today.month:02d}/{filename}"


class MediaFile(models.Model):
    TYPE_IMAGE = "image"
    TYPE_PDF   = "pdf"
    TYPE_DOCX  = "docx"
    TYPE_EXCEL = "excel"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_IMAGE, "Hình ảnh"),
        (TYPE_PDF,   "PDF"),
        (TYPE_DOCX,  "Word (.docx)"),
        (TYPE_EXCEL, "Excel (.xlsx)"),
        (TYPE_OTHER, "Khác"),
    ]

    ALLOWED_EXTENSIONS = {
        # Images
        ".jpg": TYPE_IMAGE, ".jpeg": TYPE_IMAGE, ".png": TYPE_IMAGE,
        ".gif": TYPE_IMAGE, ".webp": TYPE_IMAGE, ".bmp": TYPE_IMAGE,
        ".svg": TYPE_IMAGE,
        # Documents
        ".pdf":  TYPE_PDF,
        ".doc":  TYPE_DOCX, ".docx": TYPE_DOCX,
        ".xls":  TYPE_EXCEL, ".xlsx": TYPE_EXCEL, ".csv": TYPE_EXCEL,
    }

    MAX_UPLOAD_SIZE_MB = 20  # MB

    file       = models.FileField(upload_to=_upload_path, verbose_name="File")
    name       = models.CharField(max_length=255, verbose_name="Tên file")
    file_type  = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_OTHER,
        db_index=True,
        verbose_name="Loại file",
    )
    mime_type  = models.CharField(max_length=120, blank=True, verbose_name="MIME type")
    file_size  = models.PositiveIntegerField(default=0, verbose_name="Kích thước (bytes)")
    width      = models.PositiveIntegerField(null=True, blank=True, verbose_name="Chiều rộng (px)")
    height     = models.PositiveIntegerField(null=True, blank=True, verbose_name="Chiều cao (px)")

    alt_text   = models.CharField(max_length=255, blank=True, verbose_name="Alt text")
    note       = models.TextField(blank=True, verbose_name="Ghi chú")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="uploaded_media",
        verbose_name="Người upload",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "media_library_file"
        ordering = ["-created_at"]
        verbose_name = "File media"
        verbose_name_plural = "Thư viện file media"

    def __str__(self) -> str:
        return self.name

    @property
    def url(self) -> str:
        try:
            return self.file.url
        except Exception:
            return ""

    @property
    def file_size_display(self) -> str:
        size = self.file_size or 0
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    @property
    def is_image(self) -> bool:
        return self.file_type == self.TYPE_IMAGE

    @classmethod
    def detect_file_type(cls, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        return cls.ALLOWED_EXTENSIONS.get(ext, cls.TYPE_OTHER)
