"""
hrm/models/doctor_schedule.py
==============================
Lịch làm việc của bác sĩ theo từng tuần.
Mỗi bản ghi = 1 bác sĩ × 1 tuần (week_start luôn là thứ Hai).
schedule_json lưu ca làm việc theo ngày:
  {
    "mon": "morning",      # "morning" | "afternoon" | "all_day" | null
    "tue": "all_day",
    "wed": null,
    "thu": "morning",
    "fri": "afternoon",
    "sat": null,
    "sun": null
  }
"""

from django.db import models


SHIFT_CHOICES = [
    ("morning",   "Ca sáng"),
    ("afternoon", "Ca chiều"),
    ("all_day",   "Cả ngày"),
]

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DAY_LABELS = {
    "mon": "Thứ 2",
    "tue": "Thứ 3",
    "wed": "Thứ 4",
    "thu": "Thứ 5",
    "fri": "Thứ 6",
    "sat": "Thứ 7",
    "sun": "CN",
}

SHIFT_LABELS = {
    "morning":   "Sáng",
    "afternoon": "Chiều",
    "all_day":   "Cả ngày",
}


class DoctorSchedule(models.Model):
    """Lịch làm việc bác sĩ theo tuần."""

    doctor = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="doctor_schedules",
        verbose_name="Bác sĩ",
    )
    week_start = models.DateField(
        db_index=True,
        verbose_name="Ngày đầu tuần (Thứ Hai)",
        help_text="Luôn là thứ Hai của tuần tương ứng.",
    )
    schedule_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Lịch theo ngày",
        help_text='{"mon": "morning", "tue": "all_day", "wed": null, ...}',
    )
    note = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Ghi chú",
    )
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doctor_schedules_created",
        verbose_name="Người tạo",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hrm_doctor_schedule"
        unique_together = [("doctor", "week_start")]
        ordering = ["-week_start", "doctor__full_name"]
        verbose_name = "Lịch làm việc bác sĩ"
        verbose_name_plural = "Lịch làm việc bác sĩ"
        indexes = [
            models.Index(fields=["week_start"], name="hrm_doc_sched_week_idx"),
        ]

    def __str__(self):
        return f"{self.doctor.full_name} — tuần {self.week_start.strftime('%d/%m/%Y')}"

    def get_schedule_display(self):
        """Trả về dict {day_key: {label, shift_label}} để hiển thị."""
        result = {}
        sched = self.schedule_json or {}
        for day in DAY_KEYS:
            shift = sched.get(day)
            result[day] = {
                "day_label": DAY_LABELS[day],
                "shift": shift,
                "shift_label": SHIFT_LABELS.get(shift, ""),
                "is_working": bool(shift),
            }
        return result
