from django.conf import settings
from django.db import models


class EventType(models.TextChoices):
    # Phê duyệt
    APPROVAL_SUBMITTED  = "approval.submitted",  "Nộp phê duyệt"
    APPROVAL_APPROVED   = "approval.approved",   "Phê duyệt thành công"
    APPROVAL_REJECTED   = "approval.rejected",   "Bị từ chối"
    APPROVAL_RECALLED   = "approval.recalled",   "Thu hồi yêu cầu"
    # Hợp đồng / Báo giá
    CONTRACT_APPROVED   = "contract.approved",   "Hợp đồng được duyệt"
    QUOTATION_RETURNED  = "quotation.returned",  "Báo giá bị trả lại"
    PAYMENT_REJECTED    = "payment.rejected",    "Phiếu thanh toán từ chối"
    # Lịch khám
    SCHEDULE_CHANGED    = "schedule.changed",    "Lịch khám thay đổi"
    # Nhắc việc nội bộ
    REMINDER            = "reminder",            "Nhắc việc"


class NotificationLevel(models.TextChoices):
    INFO    = "info",    "Thông tin"
    SUCCESS = "success", "Thành công"
    WARNING = "warning", "Cảnh báo"
    DANGER  = "danger",  "Quan trọng"


class Notification(models.Model):
    """
    Thông báo in-app. Được tạo bởi push() trong service layer,
    sau đó broadcast qua WebSocket tới browser của recipient.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Người nhận",
    )
    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
        db_index=True,
        verbose_name="Loại sự kiện",
    )
    level = models.CharField(
        max_length=10,
        choices=NotificationLevel.choices,
        default=NotificationLevel.INFO,
        verbose_name="Mức độ",
    )
    title   = models.CharField(max_length=120, verbose_name="Tiêu đề")
    body    = models.TextField(blank=True, verbose_name="Nội dung")
    url     = models.CharField(max_length=500, blank=True, verbose_name="Đường dẫn")
    is_read = models.BooleanField(default=False, db_index=True)

    # Metadata tuỳ chọn — lưu payload gốc để sau này mở rộng
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = "notifications_notification"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["recipient", "is_read", "-created_at"],
                         name="notif_recipient_unread_idx"),
        ]
        verbose_name = "Thông báo"
        verbose_name_plural = "Thông báo"

    def __str__(self):
        return f"[{self.level}] {self.title} → {self.recipient_id}"

    def as_dict(self) -> dict:
        """Serialize để gửi qua WebSocket."""
        return {
            "id":         self.pk,
            "event_type": self.event_type,
            "level":      self.level,
            "title":      self.title,
            "body":       self.body,
            "url":        self.url,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
        }
