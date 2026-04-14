from django.conf import settings
from django.db import models


class ImplementationPlan(models.Model):
    contract = models.OneToOneField(
        "contract.Contract",
        on_delete=models.CASCADE,
        related_name="implementation_plan",
    )
    rows_json = models.JSONField(default=list, blank=True)

    # True = hiển thị ra danh sách triển khai chính thức
    # False = bản nháp, chỉ người tạo và Executive xem được qua link trực tiếp
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Đã công khai",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_implementation_plan"
        ordering = ["-id"]
        verbose_name = "Kế hoạch triển khai"
        verbose_name_plural = "Kế hoạch triển khai"

    def __str__(self):
        return f"Kế hoạch triển khai - {self.contract.contract_number or self.contract_id}"


class ImplementationPlanLog(models.Model):
    ACTION_EDIT = "edit"
    ACTION_CONFIRM = "confirm"
    ACTION_UNLOCK = "unlock"

    ACTION_CHOICES = (
        (ACTION_EDIT, "Chỉnh sửa"),
        (ACTION_CONFIRM, "Xác nhận"),
        (ACTION_UNLOCK, "Gỡ xác nhận / mở khóa"),
    )

    plan = models.ForeignKey(
        "contract.ImplementationPlan",
        on_delete=models.CASCADE,
        related_name="logs",
    )
    row_stt = models.PositiveIntegerField(null=True, blank=True)
    row_owner = models.CharField(max_length=255, blank=True, default="")
    row_category = models.CharField(max_length=255, blank=True, default="")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    department_key = models.CharField(max_length=50, blank=True, default="")
    department_label = models.CharField(max_length=120, blank=True, default="")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contract_implementation_logs",
    )
    actor_name = models.CharField(max_length=255, blank=True, default="")

    detail_before = models.TextField(blank=True, default="")
    detail_after = models.TextField(blank=True, default="")
    note_before = models.TextField(blank=True, default="")
    note_after = models.TextField(blank=True, default="")
    extra_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contract_implementation_plan_log"
        ordering = ["-created_at", "-id"]
        verbose_name = "Log kế hoạch triển khai"
        verbose_name_plural = "Log kế hoạch triển khai"
        indexes = [
            models.Index(fields=["plan", "row_stt", "-created_at"], name="impl_log_plan_row_idx"),
            models.Index(fields=["plan", "action", "-created_at"], name="impl_log_plan_act_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - dòng {self.row_stt or '-'} - {self.plan_id}"
