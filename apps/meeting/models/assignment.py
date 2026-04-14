from django.conf import settings
from django.db import models

from apps.meeting.domain.enums import DEPARTMENT_CHOICES, ShiftType


class DeptAssignment(models.Model):
    """
    Phân công của một phòng ban trong buổi họp.
    Mỗi session có nhiều DeptAssignment (1 per phòng ban tham gia).
    Trưởng phòng (lead_user) xác nhận bằng cách set confirmed=True.
    """

    session = models.ForeignKey(
        "meeting.MeetingSession",
        on_delete=models.CASCADE,
        related_name="dept_assignments",
        verbose_name="Buổi họp",
    )
    department = models.CharField(
        max_length=20,
        choices=DEPARTMENT_CHOICES,
        db_index=True,
        verbose_name="Phòng ban",
    )
    lead_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_dept_assignments",
        verbose_name="Trưởng phòng / Đại diện",
    )

    # Xác nhận trong buổi họp
    confirmed = models.BooleanField(default=False, db_index=True, verbose_name="Đã xác nhận")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_dept_assignments",
        verbose_name="Xác nhận bởi",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm xác nhận")

    # Ghi chú nội bộ phòng ban
    notes = models.TextField(blank=True, verbose_name="Ghi chú")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_dept_assignment"
        unique_together = [("session", "department")]
        ordering = ["department"]
        verbose_name = "Phân công phòng ban"
        verbose_name_plural = "Phân công phòng ban"

    def __str__(self):
        return f"{self.get_department_display()} – {self.session.title}"

    @property
    def dept_label(self) -> str:
        return self.get_department_display()

    @property
    def staff_count(self) -> int:
        return self.staff_shifts.count()

    @property
    def am_count(self) -> int:
        return self.staff_shifts.filter(shift__in=[ShiftType.AM, ShiftType.FULL]).count()

    @property
    def pm_count(self) -> int:
        return self.staff_shifts.filter(shift__in=[ShiftType.PM, ShiftType.FULL]).count()

    @property
    def unconfirmed_shifts(self):
        return self.staff_shifts.filter(confirmed=False)


class StaffShift(models.Model):
    """
    Chi tiết ca làm việc của một nhân viên trong ngày KSK.
    Gắn với DeptAssignment, không gắn trực tiếp với session
    để tránh denormalization.
    """

    dept_assignment = models.ForeignKey(
        DeptAssignment,
        on_delete=models.CASCADE,
        related_name="staff_shifts",
        verbose_name="Phân công phòng ban",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meeting_staff_shifts",
        verbose_name="Nhân viên",
    )

    # Vai trò trong ngày KSK (ví dụ: "Điều phối tổng", "Check-in tablet")
    role_in_day = models.CharField(max_length=255, blank=True, verbose_name="Vai trò trong ngày")

    shift = models.CharField(
        max_length=5,
        choices=[(s.value, s.value) for s in ShiftType],
        default=ShiftType.FULL,
        verbose_name="Ca",
    )
    time_from = models.TimeField(null=True, blank=True, verbose_name="Từ giờ")
    time_to = models.TimeField(null=True, blank=True, verbose_name="Đến giờ")

    # Xác nhận cá nhân
    confirmed = models.BooleanField(default=True, verbose_name="Đã xác nhận")
    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_staff_shift"
        unique_together = [("dept_assignment", "user")]
        ordering = ["shift", "user__last_name"]
        verbose_name = "Ca làm việc nhân viên"
        verbose_name_plural = "Ca làm việc nhân viên"

    def __str__(self):
        return f"{self.user} – {self.get_shift_display()} ({self.dept_assignment.dept_label})"

    @property
    def shift_display(self) -> str:
        if self.time_from and self.time_to:
            return f"{self.time_from.strftime('%H:%M')}–{self.time_to.strftime('%H:%M')}"
        return self.get_shift_display()
