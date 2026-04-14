"""
helpdesk/migrations/0001_initial.py
"""
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tasks", "0002_alter_task_options_alter_taskactivity_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Ticket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("subject", models.CharField(max_length=255, verbose_name="Tiêu đề yêu cầu")),
                ("category", models.CharField(
                    choices=[
                        ("DATA_CORRECTION", "Chỉnh sửa dữ liệu"),
                        ("CATALOG_CHANGE", "Thay đổi giá / Danh mục"),
                        ("UI_CHANGE", "Thay đổi giao diện / biểu mẫu"),
                        ("SYSTEM_BUG", "Báo lỗi hệ thống"),
                        ("PERMISSION", "Phân quyền / tài khoản"),
                        ("REPORT", "Yêu cầu báo cáo"),
                        ("OTHER", "Khác"),
                    ],
                    default="OTHER", max_length=20, verbose_name="Loại yêu cầu",
                )),
                ("priority", models.CharField(
                    choices=[
                        ("LOW", "Thấp"), ("MEDIUM", "Trung bình"),
                        ("HIGH", "Cao"), ("URGENT", "Khẩn cấp"),
                    ],
                    default="MEDIUM", max_length=8, verbose_name="Độ ưu tiên",
                )),
                ("status", models.CharField(
                    choices=[
                        ("OPEN", "Mới – Chờ tiếp nhận"),
                        ("IN_PROGRESS", "Đang xử lý"),
                        ("PENDING_CONFIRM", "Chờ xác nhận"),
                        ("CLOSED", "Đã đóng"),
                    ],
                    db_index=True, default="OPEN", max_length=20, verbose_name="Trạng thái",
                )),
                ("closed_at", models.DateTimeField(blank=True, null=True, verbose_name="Thời điểm đóng")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="helpdesk_tickets_assigned",
                    to=settings.AUTH_USER_MODEL, verbose_name="IT phụ trách",
                )),
                ("closed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="helpdesk_tickets_closed",
                    to=settings.AUTH_USER_MODEL, verbose_name="Người xác nhận đóng",
                )),
                ("created_by", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="helpdesk_tickets_created",
                    to=settings.AUTH_USER_MODEL, verbose_name="Người gửi",
                )),
                ("linked_task", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="helpdesk_ticket",
                    to="tasks.task", verbose_name="Công việc liên kết",
                )),
            ],
            options={
                "verbose_name": "Ticket yêu cầu IT",
                "verbose_name_plural": "Ticket yêu cầu IT",
                "db_table": "helpdesk_ticket",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="helpdesk_ti_status_idx"),
                    models.Index(fields=["created_by", "status"], name="helpdesk_ti_creator_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TicketMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField(verbose_name="Nội dung")),
                ("attachments_json", models.JSONField(blank=True, default=list)),
                ("is_system_event", models.BooleanField(default=False)),
                ("event_type", models.CharField(blank=True, max_length=40)),
                ("event_detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sender", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="helpdesk_messages",
                    to=settings.AUTH_USER_MODEL, verbose_name="Người gửi",
                )),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="messages",
                    to="helpdesk.ticket", verbose_name="Ticket",
                )),
            ],
            options={
                "verbose_name": "Tin nhắn",
                "db_table": "helpdesk_ticket_message",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="TicketAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="helpdesk/attachments/%Y/%m/")),
                ("filename", models.CharField(max_length=255)),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="attachment_files",
                    to="helpdesk.ticketmessage",
                )),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="attachment_files",
                    to="helpdesk.ticket",
                )),
                ("uploaded_by", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Tệp đính kèm",
                "db_table": "helpdesk_ticket_attachment",
            },
        ),
    ]
