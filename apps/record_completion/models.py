"""
apps/record_completion/models.py
"""

from datetime import date

from django.conf import settings
from django.db import models


TOTAL_STEPS = 6

STEP_CONFIGS = [
    {
        "index": 0, "key": "checklist_review",
        "label": "Kiểm tra checklist", "short_label": "Checklist",
        "description": "Thư ký y khoa dò checklist dịch vụ, ghi chú mục chưa / không thực hiện",
        "actor_groups": ["Medical Secretary", "Secretary", "Receptionist"],
        "icon": "fa-solid fa-list-check",
        "color": "#6366f1", "bg_light": "#eef2ff", "border_color": "#c7d2fe",
        "has_note": True, "note_required": False, "needs_scan": False,
    },
    {
        "index": 1, "key": "nurse_confirm",
        "label": "Điều dưỡng xác nhận", "short_label": "Điều dưỡng",
        "description": "Điều dưỡng xác nhận các phần chuyên môn và kết luận đã đủ",
        "actor_groups": ["Nurse", "Nurses"],
        "icon": "fa-solid fa-user-nurse",
        "color": "#0891b2", "bg_light": "#ecfeff", "border_color": "#a5f3fc",
        "has_note": False, "note_required": False, "needs_scan": False,
    },
    {
        "index": 2, "key": "doctor_ecg",
        "label": "BS nội xác nhận ĐTĐ", "short_label": "BS nội – ĐTĐ",
        "description": "Bác sỹ nội xác nhận đã đọc điện tim; thư ký in phiếu và dán hồ sơ",
        "actor_groups": ["Doctor", "Doctors", "Internal Doctor"],
        "icon": "fa-solid fa-heart-pulse",
        "color": "#dc2626", "bg_light": "#fef2f2", "border_color": "#fecaca",
        "has_note": False, "note_required": False, "needs_scan": False,
    },
    {
        "index": 3, "key": "director_confirm",
        "label": "GĐ YK xác nhận", "short_label": "GĐ YK xác nhận",
        "description": "Bác sỹ giám đốc y khoa xác nhận mọi thông tin khám đã chuẩn",
        "actor_groups": ["Medical Director", "Director"],
        "icon": "fa-solid fa-user-doctor",
        "color": "#7c3aed", "bg_light": "#f5f3ff", "border_color": "#ddd6fe",
        "has_note": False, "note_required": False, "needs_scan": False,
    },
    {
        "index": 4, "key": "paper_signed",
        "label": "GĐ YK ký hồ sơ", "short_label": "Ký hồ sơ",
        "description": "Thư ký đưa hồ sơ giấy cho GĐ YK ký, click xác nhận đã ký",
        "actor_groups": ["Medical Secretary", "Secretary", "Receptionist"],
        "icon": "fa-solid fa-pen-to-square",
        "color": "#d97706", "bg_light": "#fffbeb", "border_color": "#fde68a",
        "has_note": False, "note_required": False, "needs_scan": False,
    },
    {
        "index": 5, "key": "dispatched",
        "label": "Gửi bưu điện", "short_label": "Gửi bưu điện",
        "description": "Thư ký quét mã BN xác nhận hồ sơ được gửi đi bưu điện",
        "actor_groups": ["Medical Secretary", "Secretary", "Receptionist"],
        "icon": "fa-solid fa-paper-plane",
        "color": "#059669", "bg_light": "#ecfdf5", "border_color": "#a7f3d0",
        "has_note": False, "note_required": False, "needs_scan": True,
    },
]

COMPLETED_STAGE = {
    "index": 6, "key": "completed",
    "label": "Hoàn tất", "short_label": "Hoàn tất",
    "description": "Hồ sơ đã hoàn tất toàn bộ quy trình",
    "icon": "fa-solid fa-circle-check",
    "color": "#16a34a", "bg_light": "#f0fdf4", "border_color": "#bbf7d0",
}

OVERDUE_DAYS = 7


class RecordCompletion(models.Model):
    checkin_record = models.OneToOneField(
        "reception.CheckInRecord",
        on_delete=models.CASCADE,
        related_name="record_completion",
        verbose_name="Bản ghi check-in",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="record_completions",
        verbose_name="Công ty",
        db_index=True,
    )
    current_step = models.PositiveSmallIntegerField(
        default=0, db_index=True, verbose_name="Bước hiện tại",
    )
    is_completed = models.BooleanField(
        default=False, db_index=True, verbose_name="Hoàn tất",
    )
    checklist_note = models.TextField(blank=True, verbose_name="Ghi chú checklist")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "record_completion"
        verbose_name = "Hoàn tất hồ sơ"
        verbose_name_plural = "Hoàn tất hồ sơ"
        ordering = ["checkin_record__exam_date", "checkin_record__snapshot_ho_ten"]
        indexes = [
            models.Index(fields=["company", "is_completed"], name="rc_company_completed_idx"),
            models.Index(fields=["current_step", "is_completed"], name="rc_step_completed_idx"),
        ]

    def __str__(self):
        return (
            f"{self.checkin_record.snapshot_ma_bn} – "
            f"{self.checkin_record.snapshot_ho_ten} (bước {self.current_step})"
        )

    @property
    def is_overdue(self) -> bool:
        if self.is_completed:
            return False
        return (date.today() - self.checkin_record.exam_date).days > OVERDUE_DAYS

    @property
    def step_config(self):
        if self.current_step < TOTAL_STEPS:
            return STEP_CONFIGS[self.current_step]
        return COMPLETED_STAGE

    @property
    def prev_step_config(self):
        if self.current_step > 0:
            return STEP_CONFIGS[self.current_step - 1]
        return None


# ── Log action constants ──────────────────────────────────────────────────────

LOG_ACTION_ADVANCE = "ADVANCE"
LOG_ACTION_RETURN  = "RETURN"

LOG_ACTION_CHOICES = [
    (LOG_ACTION_ADVANCE, "Xác nhận tiến"),
    (LOG_ACTION_RETURN,  "Trả về bước trước"),
]


class RecordCompletionLog(models.Model):
    """Audit log mỗi lần xác nhận hoặc trả về một bước."""

    record_completion = models.ForeignKey(
        RecordCompletion,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Hồ sơ",
    )
    step = models.PositiveSmallIntegerField(verbose_name="Bước")
    action = models.CharField(
        max_length=10,
        choices=LOG_ACTION_CHOICES,
        default=LOG_ACTION_ADVANCE,
        db_index=True,
        verbose_name="Hành động",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="record_completion_logs",
        verbose_name="Người thực hiện",
    )
    note = models.TextField(blank=True, verbose_name="Ghi chú / Lý do")
    confirmed_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        db_table = "record_completion_log"
        verbose_name = "Log hoàn tất hồ sơ"
        verbose_name_plural = "Log hoàn tất hồ sơ"
        ordering = ["confirmed_at"]   # chronological – thay từ ["step", "confirmed_at"]
        indexes = [
            models.Index(fields=["record_completion", "step"], name="rcl_completion_step_idx"),
            models.Index(fields=["record_completion", "action"], name="rcl_completion_action_idx"),
        ]

    def __str__(self):
        return (
            f"Step {self.step} [{self.action}] – {self.record_completion} "
            f"– {self.actor} @ {self.confirmed_at:%d/%m/%Y %H:%M}"
        )

    @property
    def is_return(self):
        return self.action == LOG_ACTION_RETURN
