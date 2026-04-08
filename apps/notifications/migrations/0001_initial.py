import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người nhận",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("approval.submitted",  "Nộp phê duyệt"),
                            ("approval.approved",   "Phê duyệt thành công"),
                            ("approval.rejected",   "Bị từ chối"),
                            ("approval.recalled",   "Thu hồi yêu cầu"),
                            ("contract.approved",   "Hợp đồng được duyệt"),
                            ("quotation.returned",  "Báo giá bị trả lại"),
                            ("payment.rejected",    "Phiếu thanh toán từ chối"),
                            ("schedule.changed",    "Lịch khám thay đổi"),
                            ("reminder",            "Nhắc việc"),
                        ],
                        db_index=True,
                        max_length=40,
                        verbose_name="Loại sự kiện",
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("info",    "Thông tin"),
                            ("success", "Thành công"),
                            ("warning", "Cảnh báo"),
                            ("danger",  "Quan trọng"),
                        ],
                        default="info",
                        max_length=10,
                        verbose_name="Mức độ",
                    ),
                ),
                ("title",      models.CharField(max_length=120, verbose_name="Tiêu đề")),
                ("body",       models.TextField(blank=True, verbose_name="Nội dung")),
                ("url",        models.CharField(blank=True, max_length=500, verbose_name="Đường dẫn")),
                ("is_read",    models.BooleanField(db_index=True, default=False)),
                ("meta",       models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Thông báo",
                "verbose_name_plural": "Thông báo",
                "db_table": "notifications_notification",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="notif_recipient_unread_idx",
            ),
        ),
    ]
