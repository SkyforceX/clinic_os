"""
hrm/models/work_schedule.py
============================
Lịch làm việc toàn phòng khám (thay thế DoctorSchedule cũ).

Mỗi bản ghi = 1 nhân viên × 1 ngày cụ thể × 1 mã ca.

Mã ca (shift):
  F  — Cả ngày (full day)
  S  — Ca sáng
  C  — Ca chiều
  L  — Nghỉ lễ / nghỉ tết
  O  — Không làm việc (off)
  null / blank — Chưa đăng ký

Business rules:
  - HR Admin có thể chỉnh bất kỳ lúc nào.
  - Nhân viên tự đăng ký và sửa trước 0:00 ngày được đăng ký.
  - Mọi thay đổi được ghi vào WorkScheduleLog.
"""

from django.conf import settings
from django.db import models


SHIFT_FULL   = "F"
SHIFT_MORNING= "S"
SHIFT_AFTERNOON = "C"
SHIFT_HOLIDAY= "L"
SHIFT_OFF    = "O"

SHIFT_CHOICES = [
    (SHIFT_FULL,      "Cả ngày"),
    (SHIFT_MORNING,   "Ca sáng"),
    (SHIFT_AFTERNOON, "Ca chiều"),
    (SHIFT_HOLIDAY,   "Nghỉ lễ / Tết"),
    (SHIFT_OFF,       "Không làm việc"),
]

SHIFT_DISPLAY = {
    SHIFT_FULL:      {"label": "F", "title": "Cả ngày",   "css": "shift-f"},
    SHIFT_MORNING:   {"label": "S", "title": "Ca sáng",   "css": "shift-s"},
    SHIFT_AFTERNOON: {"label": "C", "title": "Ca chiều",  "css": "shift-c"},
    SHIFT_HOLIDAY:   {"label": "L", "title": "Nghỉ lễ",   "css": "shift-l"},
    SHIFT_OFF:       {"label": "O", "title": "Không làm", "css": "shift-o"},
}


class WorkSchedule(models.Model):
    """Lịch làm việc 1 nhân viên × 1 ngày."""

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="work_schedules",
        verbose_name="Nhân viên",
    )
    schedule_date = models.DateField(
        db_index=True,
        verbose_name="Ngày làm việc",
    )
    shift = models.CharField(
        max_length=1,
        choices=SHIFT_CHOICES,
        blank=True,
        default="",
        verbose_name="Ca làm việc",
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Ghi chú",
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_schedules_registered",
        verbose_name="Người đăng ký",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hrm_work_schedule"
        unique_together = [("employee", "schedule_date")]
        ordering = ["schedule_date", "employee__department__display_order", "employee__full_name"]
        verbose_name = "Lịch làm việc"
        verbose_name_plural = "Lịch làm việc toàn phòng khám"
        indexes = [
            models.Index(fields=["schedule_date"], name="hrm_ws_date_idx"),
            models.Index(fields=["employee", "schedule_date"], name="hrm_ws_emp_date_idx"),
        ]

    def __str__(self):
        return f"{self.employee.full_name} — {self.schedule_date} — {self.shift or '—'}"

    @property
    def shift_display(self):
        return SHIFT_DISPLAY.get(self.shift, {"label": "", "title": "Chưa đăng ký", "css": "shift-empty"})


class WorkScheduleLog(models.Model):
    """Audit log mọi thay đổi lịch làm việc."""

    work_schedule = models.ForeignKey(
        WorkSchedule,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Lịch làm việc",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="work_schedule_logs",
        verbose_name="Người thực hiện",
    )
    old_shift = models.CharField(max_length=1, blank=True, verbose_name="Ca cũ")
    new_shift = models.CharField(max_length=1, blank=True, verbose_name="Ca mới")
    note      = models.CharField(max_length=200, blank=True, verbose_name="Ghi chú")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hrm_work_schedule_log"
        ordering = ["-created_at"]
        verbose_name = "Log lịch làm việc"

    def __str__(self):
        return f"{self.actor} | {self.old_shift} → {self.new_shift} @ {self.created_at:%d/%m/%Y %H:%M}"
