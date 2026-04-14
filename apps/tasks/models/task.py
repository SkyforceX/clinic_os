"""
tasks/models/task.py
======================
Model giao việc và theo dõi tiến độ.

Pipeline các giai đoạn (stage) hiển thị theo chiều ngang.
Công việc trong mỗi giai đoạn xếp theo chiều dọc.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TaskStage(models.TextChoices):
    """Pipeline stages — thứ tự từ trái sang phải."""
    TODO        = "TODO",        "Cần làm"
    IN_PROGRESS = "IN_PROGRESS", "Đang thực hiện"
    IN_REVIEW   = "IN_REVIEW",   "Chờ kiểm tra"
    DONE        = "DONE",        "Hoàn thành"
    CANCELLED   = "CANCELLED",   "Đã hủy"


class TaskPriority(models.TextChoices):
    LOW    = "LOW",    "Thấp"
    MEDIUM = "MEDIUM", "Trung bình"
    HIGH   = "HIGH",   "Cao"
    URGENT = "URGENT", "Khẩn cấp"


# ── Task ──────────────────────────────────────────────────────────────────────

class Task(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    title       = models.CharField(max_length=255, verbose_name="Tiêu đề")
    description = models.TextField(blank=True, verbose_name="Mô tả chi tiết")

    stage    = models.CharField(
        max_length=15, choices=TaskStage.choices, default=TaskStage.TODO,
        db_index=True, verbose_name="Giai đoạn",
    )
    priority = models.CharField(
        max_length=8, choices=TaskPriority.choices, default=TaskPriority.MEDIUM,
        db_index=True, verbose_name="Độ ưu tiên",
    )

    # ── Phân công ──────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="tasks_created",
        verbose_name="Người tạo",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tasks_assigned",
        verbose_name="Người nhận việc",
    )
    # Phụ trách thêm (nhiều người theo dõi)
    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="tasks_watching",
        verbose_name="Người theo dõi",
    )

    # ── Thời gian ──────────────────────────────────────────────────────────────
    due_date      = models.DateField(null=True, blank=True, verbose_name="Hạn hoàn thành")
    start_date    = models.DateField(null=True, blank=True, verbose_name="Ngày bắt đầu")
    completed_at  = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm hoàn thành")
    estimated_hours = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name="Giờ ước tính",
    )
    actual_hours  = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name="Giờ thực tế",
    )

    # ── Sắp xếp trong pipeline ─────────────────────────────────────────────────
    stage_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Thứ tự trong giai đoạn")

    # ── Metadata ──────────────────────────────────────────────────────────────
    tags        = models.CharField(max_length=255, blank=True, verbose_name="Tags (ngăn cách bằng dấu phẩy)")
    attachments = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tasks_task"
        ordering = ["stage_order", "-priority", "due_date"]
        verbose_name = "Công việc"
        verbose_name_plural = "Công việc"
        indexes = [
            models.Index(fields=["stage", "stage_order"]),
            models.Index(fields=["assignee", "stage"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self) -> bool:
        if self.stage in (TaskStage.DONE, TaskStage.CANCELLED):
            return False
        return bool(self.due_date and self.due_date < timezone.now().date())

    @property
    def is_done(self) -> bool:
        return self.stage == TaskStage.DONE

    @property
    def is_cancelled(self) -> bool:
        return self.stage == TaskStage.CANCELLED

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()] if self.tags else []


# ── TaskComment ────────────────────────────────────────────────────────────────

class TaskComment(models.Model):
    task    = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="task_comments",
    )
    body       = models.TextField(verbose_name="Nội dung")
    is_internal = models.BooleanField(default=False, verbose_name="Ghi chú nội bộ")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tasks_task_comment"
        ordering = ["created_at"]
        verbose_name = "Bình luận"

    def __str__(self):
        return f"Comment by {self.author_id} on Task {self.task_id}"


# ── TaskActivity (audit log) ───────────────────────────────────────────────────

class TaskActivity(models.Model):
    class Action(models.TextChoices):
        CREATED   = "CREATED",   "Tạo mới"
        UPDATED   = "UPDATED",   "Cập nhật"
        MOVED     = "MOVED",     "Chuyển giai đoạn"
        ASSIGNED  = "ASSIGNED",  "Phân công"
        COMMENTED = "COMMENTED", "Bình luận"
        COMPLETED = "COMPLETED", "Hoàn thành"
        CANCELLED = "CANCELLED", "Hủy"
        REOPENED  = "REOPENED",  "Mở lại"

    task      = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="activities")
    actor     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="task_activities",
    )
    action    = models.CharField(max_length=12, choices=Action.choices)
    detail    = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks_task_activity"
        ordering = ["-created_at"]
        verbose_name = "Lịch sử công việc"
