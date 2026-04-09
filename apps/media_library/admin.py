from django.contrib import admin
from django.utils.html import format_html

from apps.media_library.models import MediaFile


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display  = ("thumbnail_preview", "name", "file_type", "file_size_display", "created_by", "created_at")
    list_filter   = ("file_type", "created_at")
    search_fields = ("name", "alt_text", "note")
    readonly_fields = ("file_size", "mime_type", "width", "height", "created_at", "image_preview_large")
    ordering      = ("-created_at",)

    fieldsets = (
        ("Thông tin file", {
            "fields": ("file", "name", "file_type", "mime_type", "file_size", "width", "height"),
        }),
        ("Nội dung", {
            "fields": ("alt_text", "note", "image_preview_large"),
        }),
        ("Hệ thống", {
            "fields": ("created_by", "created_at"),
            "classes": ("collapse",),
        }),
    )

    def thumbnail_preview(self, obj: MediaFile):
        if obj.is_image and obj.url:
            return format_html(
                '<img src="{}" style="height:40px;width:auto;object-fit:cover;border-radius:4px" />',
                obj.url,
            )
        icons = {
            MediaFile.TYPE_PDF:   "📄",
            MediaFile.TYPE_DOCX:  "📝",
            MediaFile.TYPE_EXCEL: "📊",
        }
        return icons.get(obj.file_type, "📎")
    thumbnail_preview.short_description = "Xem trước"

    def image_preview_large(self, obj: MediaFile):
        if obj.is_image and obj.url:
            return format_html(
                '<img src="{}" style="max-width:400px;max-height:300px;object-fit:contain" />',
                obj.url,
            )
        return "—"
    image_preview_large.short_description = "Xem ảnh"
