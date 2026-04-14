import uuid as _uuid
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
            name="Task",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("uuid",        models.UUIDField(default=_uuid.uuid4, editable=False, unique=True)),
                ("title",       models.CharField(max_length=255, verbose_name="Tiêu đề")),
                ("description", models.TextField(blank=True)),
                ("stage",       models.CharField(max_length=15, choices=[("TODO","Cần làm"),("IN_PROGRESS","Đang thực hiện"),("IN_REVIEW","Chờ kiểm tra"),("DONE","Hoàn thành"),("CANCELLED","Đã hủy")], default="TODO", db_index=True)),
                ("priority",    models.CharField(max_length=8,  choices=[("LOW","Thấp"),("MEDIUM","Trung bình"),("HIGH","Cao"),("URGENT","Khẩn cấp")], default="MEDIUM", db_index=True)),
                ("due_date",    models.DateField(null=True, blank=True)),
                ("start_date",  models.DateField(null=True, blank=True)),
                ("completed_at",models.DateTimeField(null=True, blank=True)),
                ("estimated_hours", models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)),
                ("actual_hours",    models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)),
                ("stage_order", models.PositiveIntegerField(default=0, db_index=True)),
                ("tags",        models.CharField(max_length=255, blank=True)),
                ("attachments", models.JSONField(default=list, blank=True)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("updated_at",  models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tasks_created",  to=settings.AUTH_USER_MODEL)),
                ("assignee",   models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tasks_assigned", to=settings.AUTH_USER_MODEL)),
                ("watchers",   models.ManyToManyField(blank=True, related_name="tasks_watching", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "tasks_task", "ordering": ["stage_order", "-priority", "due_date"]},
        ),
        migrations.AddIndex(model_name="task", index=models.Index(fields=["stage","stage_order"], name="tasks_stage_order_idx")),
        migrations.AddIndex(model_name="task", index=models.Index(fields=["assignee","stage"],   name="tasks_assignee_stage_idx")),
        migrations.AddIndex(model_name="task", index=models.Index(fields=["due_date"],            name="tasks_due_date_idx")),
        migrations.CreateModel(
            name="TaskComment",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("body",        models.TextField()),
                ("is_internal", models.BooleanField(default=False)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("updated_at",  models.DateTimeField(auto_now=True)),
                ("task",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="tasks.task")),
                ("author", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="task_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "tasks_task_comment", "ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="TaskActivity",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("action",     models.CharField(max_length=12, choices=[("CREATED","Tạo mới"),("UPDATED","Cập nhật"),("MOVED","Chuyển giai đoạn"),("ASSIGNED","Phân công"),("COMMENTED","Bình luận"),("COMPLETED","Hoàn thành"),("CANCELLED","Hủy"),("REOPENED","Mở lại")])),
                ("detail",     models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("task",  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="tasks.task")),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="task_activities", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "tasks_task_activity", "ordering": ["-created_at"]},
        ),
    ]
