"""
approvals/migrations/0003_submission_fields_and_attachment.py
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("approvals", "0002_rename_apr_type_status_idx_approvals_r_request_128e1b_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Thêm 2 field nội dung vào ApprovalRequest ───────────────────────
        migrations.AddField(
            model_name="approvalrequest",
            name="submission_title",
            field=models.CharField(
                blank=True, max_length=255, verbose_name="Tiêu đề trình duyệt"
            ),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="submission_body",
            field=models.TextField(blank=True, verbose_name="Nội dung chi tiết (HTML)"),
        ),
        # ── Model mới ApprovalAttachment ────────────────────────────────────
        migrations.CreateModel(
            name="ApprovalAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "approval_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="approvals.approvalrequest",
                        verbose_name="Yêu cầu phê duyệt",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người tải lên",
                    ),
                ),
                ("file",         models.FileField(upload_to="approvals/private/%Y/%m/", verbose_name="Tệp")),
                ("filename",     models.CharField(max_length=255, verbose_name="Tên tệp")),
                ("file_size",    models.PositiveIntegerField(default=0, verbose_name="Kích thước (bytes)")),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("created_at",   models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Tệp đính kèm phê duyệt",
                "db_table": "approvals_attachment",
                "ordering": ["created_at"],
            },
        ),
    ]
