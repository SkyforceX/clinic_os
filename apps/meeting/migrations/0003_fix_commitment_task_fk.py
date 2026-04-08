"""
Migration 0003: Đổi MeetingCommitment.task từ TextField sang FK đến tasks.Task.
Dùng string reference 'tasks.task' để tránh circular import.
Cần migrate TRƯỚC KHI chạy nếu đã có dữ liệu cũ (field task là TextField null).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0002_meetingcommitment_task"),
        ("tasks",   "0001_initial"),
    ]

    operations = [
        # 1. Xóa field TextField cũ
        migrations.RemoveField(
            model_name="meetingcommitment",
            name="task",
        ),
        # 2. Thêm FK đúng sang tasks.Task
        migrations.AddField(
            model_name="meetingcommitment",
            name="task",
            field=models.ForeignKey(
                to="tasks.task",
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="meeting_commitments",
                verbose_name="Task liên kết",
            ),
        ),
    ]
