from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.media_library.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MediaFile",
            fields=[
                ("id",        models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file",      models.FileField(upload_to=apps.media_library.models._upload_path, verbose_name="File")),
                ("name",      models.CharField(max_length=255, verbose_name="Tên file")),
                ("file_type", models.CharField(
                    choices=[
                        ("image", "Hình ảnh"),
                        ("pdf",   "PDF"),
                        ("docx",  "Word (.docx)"),
                        ("excel", "Excel (.xlsx)"),
                        ("other", "Khác"),
                    ],
                    db_index=True,
                    default="other",
                    max_length=20,
                    verbose_name="Loại file",
                )),
                ("mime_type",  models.CharField(blank=True, max_length=120, verbose_name="MIME type")),
                ("file_size",  models.PositiveIntegerField(default=0, verbose_name="Kích thước (bytes)")),
                ("width",      models.PositiveIntegerField(blank=True, null=True, verbose_name="Chiều rộng (px)")),
                ("height",     models.PositiveIntegerField(blank=True, null=True, verbose_name="Chiều cao (px)")),
                ("alt_text",   models.CharField(blank=True, max_length=255, verbose_name="Alt text")),
                ("note",       models.TextField(blank=True, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="uploaded_media",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người upload",
                )),
            ],
            options={
                "verbose_name": "File media",
                "verbose_name_plural": "Thư viện file media",
                "db_table": "media_library_file",
                "ordering": ["-created_at"],
            },
        ),
    ]
