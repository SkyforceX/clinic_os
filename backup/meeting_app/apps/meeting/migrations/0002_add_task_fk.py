"""
Migration 0002: Thêm FK từ MeetingCommitment → tasks.Task.

Chạy migration này SAU KHI tasks app đã được migrate xong.
Tách riêng để 0001_initial không bị phụ thuộc vào tasks app
(tránh circular dependency khi migrate lần đầu).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0001_initial"),
        ("tasks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="meetingcommitment",
            name="task",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_commitment",
                to="tasks.task",
                verbose_name="Task được tạo",
            ),
        ),
    ]
