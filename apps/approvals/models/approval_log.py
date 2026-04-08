from django.conf import settings
from django.db import models


class ApprovalAction(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Nộp phê duyệt"
    APPROVED  = "APPROVED",  "Phê duyệt"
    REJECTED  = "REJECTED",  "Từ chối"
    RECALLED  = "RECALLED",  "Thu hồi"


class ApprovalLog(models.Model):
    """
    Lịch sử thao tác trên một ApprovalRequest.
    Immutable — không sửa, không xóa, chỉ thêm.
    """

    approval_request = models.ForeignKey(
        "approvals.ApprovalRequest",
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Yêu cầu phê duyệt",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_logs",
        verbose_name="Người thực hiện",
    )
    action = models.CharField(
        max_length=20,
        choices=ApprovalAction.choices,
        verbose_name="Hành động",
    )
    note = models.TextField(blank=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        db_table = "approvals_log"
        ordering = ["created_at"]
        verbose_name = "Lịch sử phê duyệt"
        verbose_name_plural = "Lịch sử phê duyệt"

    def __str__(self):
        actor_name = self.actor.get_full_name() if self.actor else "—"
        return (
            f"[{self.get_action_display()}] "
            f"{actor_name} — {self.created_at.strftime('%d/%m/%Y %H:%M')}"
        )
