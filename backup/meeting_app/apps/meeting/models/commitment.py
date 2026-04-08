import hashlib
import json

from django.conf import settings
from django.db import models

from apps.meeting.domain.enums import CommitmentStatus


class MeetingCommitment(models.Model):
    """
    Cam kết / giao việc được thống nhất trong buổi họp.
    Sau khi đóng họp, mỗi commitment tự động tạo một tasks.Task
    và backfill task FK về đây (qua service close_meeting_and_create_tasks).
    """

    session = models.ForeignKey(
        "meeting.MeetingSession",
        on_delete=models.CASCADE,
        related_name="commitments",
        verbose_name="Buổi họp",
    )
    dept_assignment = models.ForeignKey(
        "meeting.DeptAssignment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commitments",
        verbose_name="Phòng ban phụ trách",
    )

    title = models.CharField(max_length=500, verbose_name="Nội dung cam kết")
    description = models.TextField(blank=True, verbose_name="Mô tả chi tiết")

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meeting_commitments",
        verbose_name="Người thực hiện",
    )
    deadline = models.DateField(null=True, blank=True, verbose_name="Deadline")

    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in CommitmentStatus],
        default=CommitmentStatus.OPEN,
        db_index=True,
        verbose_name="Trạng thái",
    )

    # FK ngược về tasks.Task — được set sau khi close_meeting_and_create_tasks()
    # Dùng string reference để tránh circular import
    task = models.OneToOneField(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_commitment",
        verbose_name="Task được tạo",
    )

    display_order = models.PositiveIntegerField(default=0, verbose_name="Thứ tự")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_commitment"
        ordering = ["display_order", "created_at"]
        verbose_name = "Cam kết trong họp"
        verbose_name_plural = "Danh sách cam kết"

    def __str__(self):
        return f"{self.title} ({self.session.title})"

    @property
    def has_task(self) -> bool:
        return self.task_id is not None

    @property
    def is_overdue(self) -> bool:
        if not self.deadline:
            return False
        from django.utils import timezone
        return self.status == CommitmentStatus.OPEN and self.deadline < timezone.now().date()


class MeetingSignature(models.Model):
    """
    Chữ ký điện tử của từng người xác nhận biên bản họp.
    doc_hash = SHA-256 của nội dung biên bản tại thời điểm ký
    → đảm bảo tính toàn vẹn, phát hiện nếu nội dung bị thay đổi sau ký.

    Không dùng PKI phức tạp — đủ giá trị pháp lý nội bộ
    theo Nghị định 130/2018/NĐ-CP về chữ ký điện tử.
    """

    session = models.ForeignKey(
        "meeting.MeetingSession",
        on_delete=models.CASCADE,
        related_name="signatures",
        verbose_name="Buổi họp",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="meeting_signatures",
        verbose_name="Người ký",
    )
    department = models.CharField(max_length=20, blank=True, verbose_name="Phòng ban đại diện")
    role_label = models.CharField(max_length=100, blank=True, verbose_name="Chức danh")

    signed_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm ký")

    # Fingerprint tài liệu
    doc_hash = models.CharField(
        max_length=64,
        verbose_name="SHA-256 hash biên bản",
        help_text="Hash của nội dung biên bản PDF tại thời điểm ký.",
    )

    # Audit info
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP address")
    user_agent = models.TextField(blank=True, verbose_name="User agent")

    class Meta:
        db_table = "meeting_signature"
        unique_together = [("session", "user")]
        ordering = ["signed_at"]
        verbose_name = "Chữ ký biên bản"
        verbose_name_plural = "Chữ ký biên bản"

    def __str__(self):
        return f"{self.user} ký – {self.session.title}"

    @classmethod
    def compute_hash(cls, session) -> str:
        """
        Tính SHA-256 từ snapshot nội dung buổi họp.
        Được gọi trong sign_meeting_minutes() service.
        Bất kỳ thay đổi nào sau khi ký sẽ làm hash không khớp.
        """
        payload = {
            "session_id": session.pk,
            "title": session.title,
            "meeting_date": str(session.meeting_date),
            "commitments": [
                {
                    "id": c.pk,
                    "title": c.title,
                    "assignee_id": c.assignee_id,
                    "deadline": str(c.deadline),
                    "status": c.status,
                }
                for c in session.commitments.order_by("pk")
            ],
            "dept_assignments": [
                {
                    "id": a.pk,
                    "department": a.department,
                    "confirmed": a.confirmed,
                }
                for a in session.dept_assignments.order_by("pk")
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
