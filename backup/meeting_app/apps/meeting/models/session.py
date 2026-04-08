from django.conf import settings
from django.db import models

from apps.meeting.domain.enums import (
    DEPARTMENT_CHOICES,
    MEETING_STEP_MAX,
    MeetingStatus,
    ParticipantRole,
)


class MeetingSession(models.Model):
    """
    Buổi họp liên phòng ban để triển khai kế hoạch (KSK, dự án, ...).

    Có thể gắn hoặc không gắn với contract cụ thể.
    Luồng: OPEN → CLOSED → SIGNED.
    Mỗi buổi họp chia tối đa MEETING_STEP_MAX bước, admin
    điều hành dùng advance_step() để chuyển bước.
    """

    # Liên kết nghiệp vụ (nullable — họp không nhất thiết phải có HĐ)
    contract = models.ForeignKey(
        "contract.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meeting_sessions",
        verbose_name="Hợp đồng liên quan",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="meeting_sessions",
        verbose_name="Doanh nghiệp",
    )

    # Thông tin buổi họp
    title = models.CharField(max_length=500, verbose_name="Tiêu đề buổi họp")
    meeting_date = models.DateField(verbose_name="Ngày họp")
    meeting_time = models.TimeField(null=True, blank=True, verbose_name="Giờ bắt đầu")
    location = models.CharField(max_length=255, blank=True, verbose_name="Địa điểm")
    note = models.TextField(blank=True, verbose_name="Ghi chú")

    # Trạng thái & bước
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in MeetingStatus],
        default=MeetingStatus.OPEN,
        db_index=True,
        verbose_name="Trạng thái",
    )
    current_step = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Bước hiện tại (1–5)",
    )

    # Người tạo
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_meeting_sessions",
        verbose_name="Người tạo",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_meeting_sessions",
        verbose_name="Người đóng họp",
    )
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm đóng họp")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_session"
        ordering = ["-meeting_date", "-created_at"]
        verbose_name = "Buổi họp"
        verbose_name_plural = "Danh sách buổi họp"

    def __str__(self):
        return f"{self.title} ({self.meeting_date})"

    # ── Computed properties ───────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self.status == MeetingStatus.OPEN

    @property
    def is_closed(self) -> bool:
        return self.status == MeetingStatus.CLOSED

    @property
    def is_signed(self) -> bool:
        return self.status == MeetingStatus.SIGNED

    @property
    def is_editable(self) -> bool:
        """Ai cũng chỉnh được khi đang OPEN."""
        return self.status == MeetingStatus.OPEN

    @property
    def step_label(self) -> str:
        from apps.meeting.domain.enums import MEETING_STEP_LABELS
        return MEETING_STEP_LABELS.get(self.current_step, "")

    @property
    def progress_pct(self) -> int:
        return int((self.current_step / MEETING_STEP_MAX) * 100)

    @property
    def has_unconfirmed_depts(self) -> bool:
        return self.dept_assignments.filter(confirmed=False).exists()

    @property
    def total_staff_count(self) -> int:
        return sum(
            a.staff_shifts.count()
            for a in self.dept_assignments.prefetch_related("staff_shifts").all()
        )


class MeetingParticipant(models.Model):
    """
    Người tham dự buổi họp.
    Tất cả participant với can_edit=True đều có thể chỉnh nội dung
    trực tiếp trong session (collaborative editing).
    """

    session = models.ForeignKey(
        MeetingSession,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Buổi họp",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meeting_participations",
        verbose_name="Người dùng",
    )
    department = models.CharField(
        max_length=20,
        choices=DEPARTMENT_CHOICES,
        blank=True,
        verbose_name="Phòng ban đại diện",
    )
    role = models.CharField(
        max_length=10,
        choices=[(r.value, r.value) for r in ParticipantRole],
        default=ParticipantRole.MEMBER,
        verbose_name="Vai trò",
    )
    can_edit = models.BooleanField(
        default=True,
        verbose_name="Được chỉnh sửa trực tiếp",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "meeting_participant"
        unique_together = [("session", "user")]
        verbose_name = "Người tham dự"
        verbose_name_plural = "Danh sách người tham dự"
        ordering = ["department", "role"]

    def __str__(self):
        return f"{self.user} – {self.session.title}"
