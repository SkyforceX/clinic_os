"""
helpdesk/models.py
===================
Hệ thống ticket gửi yêu cầu từ Executives → IT Admin.

Lifecycle:
  OPEN → IN_PROGRESS → PENDING_CONFIRM → CLOSED

Khi ticket được tạo, một Task (apps.tasks) được tự động tạo kèm.
Khi IT Admin cập nhật stage ticket → Task stage đồng bộ tương ứng.
Khi Executive xác nhận đóng ticket → ticket CLOSED, Task DONE,
  không bên nào gửi thêm được nữa.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class TicketStatus(models.TextChoices):
    OPEN             = "OPEN",             "Mới – Chờ tiếp nhận"
    IN_PROGRESS      = "IN_PROGRESS",      "Đang xử lý"
    PENDING_CONFIRM  = "PENDING_CONFIRM",  "Chờ xác nhận"
    CLOSED           = "CLOSED",           "Đã đóng"


class TicketPriority(models.TextChoices):
    LOW    = "LOW",    "Thấp"
    MEDIUM = "MEDIUM", "Trung bình"
    HIGH   = "HIGH",   "Cao"
    URGENT = "URGENT", "Khẩn cấp"


class TicketCategory(models.TextChoices):
    DATA_CORRECTION = "DATA_CORRECTION", "Chỉnh sửa dữ liệu"
    CATALOG_CHANGE  = "CATALOG_CHANGE",  "Thay đổi giá / Danh mục"
    UI_CHANGE       = "UI_CHANGE",       "Thay đổi giao diện / biểu mẫu"
    SYSTEM_BUG      = "SYSTEM_BUG",      "Báo lỗi hệ thống"
    PERMISSION      = "PERMISSION",      "Phân quyền / tài khoản"
    REPORT          = "REPORT",          "Yêu cầu báo cáo"
    OTHER           = "OTHER",           "Khác"


# Mapping TicketStatus → TaskStage (từ apps.tasks.models)
TICKET_STATUS_TO_TASK_STAGE = {
    TicketStatus.OPEN:            "TODO",
    TicketStatus.IN_PROGRESS:     "IN_PROGRESS",
    TicketStatus.PENDING_CONFIRM: "IN_REVIEW",
    TicketStatus.CLOSED:          "DONE",
}


# ─────────────────────────────────────────────────────────────────────────────
# Ticket
# ─────────────────────────────────────────────────────────────────────────────

class Ticket(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    subject  = models.CharField(max_length=255, verbose_name="Tiêu đề yêu cầu")
    category = models.CharField(
        max_length=20, choices=TicketCategory.choices,
        default=TicketCategory.OTHER,
        verbose_name="Loại yêu cầu",
    )
    priority = models.CharField(
        max_length=8, choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM,
        verbose_name="Độ ưu tiên",
    )
    status = models.CharField(
        max_length=20, choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True, verbose_name="Trạng thái",
    )

    # Liên kết Task tự động tạo khi ticket mở
    linked_task = models.OneToOneField(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="helpdesk_ticket",
        verbose_name="Công việc liên kết",
    )

    # Người tạo (Executives)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="helpdesk_tickets_created",
        verbose_name="Người gửi",
    )
    # IT Admin được assign
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="helpdesk_tickets_assigned",
        verbose_name="IT phụ trách",
    )

    # Đóng ticket
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="helpdesk_tickets_closed",
        verbose_name="Người xác nhận đóng",
    )
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm đóng")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "helpdesk_ticket"
        ordering = ["-created_at"]
        verbose_name = "Ticket yêu cầu IT"
        verbose_name_plural = "Ticket yêu cầu IT"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["created_by", "status"]),
        ]

    def __str__(self):
        return f"#{self.pk} – {self.subject}"

    @property
    def is_closed(self) -> bool:
        return self.status == TicketStatus.CLOSED

    @property
    def status_label(self) -> str:
        return dict(TicketStatus.choices).get(self.status, self.status)

    @property
    def priority_label(self) -> str:
        return dict(TicketPriority.choices).get(self.priority, self.priority)

    @property
    def category_label(self) -> str:
        return dict(TicketCategory.choices).get(self.category, self.category)


# ─────────────────────────────────────────────────────────────────────────────
# TicketMessage  (dòng thời gian)
# ─────────────────────────────────────────────────────────────────────────────

class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE,
        related_name="messages", verbose_name="Ticket",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="helpdesk_messages",
        verbose_name="Người gửi",
    )
    body = models.TextField(verbose_name="Nội dung")

    # Đính kèm file: list of {"name": str, "url": str, "size": int}
    attachments_json = models.JSONField(default=list, blank=True)

    # Sự kiện hệ thống (thay đổi trạng thái, ghi chú tự động)
    is_system_event = models.BooleanField(default=False)
    event_type      = models.CharField(max_length=40, blank=True)  # e.g. "STATUS_CHANGED"
    event_detail    = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "helpdesk_ticket_message"
        ordering = ["created_at"]
        verbose_name = "Tin nhắn"

    def __str__(self):
        return f"Message on #{self.ticket_id} by {self.sender_id}"


# ─────────────────────────────────────────────────────────────────────────────
# TicketAttachment  (file upload thực sự)
# ─────────────────────────────────────────────────────────────────────────────

class TicketAttachment(models.Model):
    ticket  = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachment_files")
    message = models.ForeignKey(
        TicketMessage, on_delete=models.CASCADE,
        null=True, blank=True, related_name="attachment_files",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    file        = models.FileField(upload_to="helpdesk/attachments/%Y/%m/")
    filename    = models.CharField(max_length=255)
    file_size   = models.PositiveIntegerField(default=0)  # bytes
    content_type = models.CharField(max_length=100, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "helpdesk_ticket_attachment"
        verbose_name = "Tệp đính kèm"

    def __str__(self):
        return self.filename

    @property
    def size_display(self) -> str:
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        return f"{self.file_size / 1024 / 1024:.1f} MB"
