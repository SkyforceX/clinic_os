from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


class PositionGroupMapping(models.Model):
    """
    Ánh xạ Chức vụ → Django Group.

    Một chức vụ có thể map tới nhiều Django Group.
    Service grant_access.py đọc bảng này khi onboard / transfer.

    Ví dụ:
      Trưởng phòng kinh doanh  →  Managers, Sales Team
      Nhân viên kinh doanh     →  Sales Team
      Bác sĩ                   →  Doctors
      Điều dưỡng               →  Nurses
      Giám đốc                 →  Executives
    """

    position = models.ForeignKey(
        "hrm.Position",
        on_delete=models.CASCADE,
        related_name="group_mappings",
        verbose_name="Chức vụ",
    )
    django_group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="position_mappings",
        verbose_name="Django Group",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        db_table = "hrm_position_group_mapping"
        unique_together = [("position", "django_group")]
        verbose_name = "Ánh xạ Chức vụ → Nhóm quyền"
        verbose_name_plural = "Ánh xạ Chức vụ → Nhóm quyền"

    def __str__(self):
        return f"{self.position.name} → {self.django_group.name}"


class AccessLogAction(models.TextChoices):
    GRANTED  = "GRANTED",  "Cấp quyền"
    REVOKED  = "REVOKED",  "Thu hồi quyền"
    ONBOARD  = "ONBOARD",  "Onboard"
    OFFBOARD = "OFFBOARD", "Offboard"
    TRANSFER = "TRANSFER", "Chuyển bộ phận"


class AccessLog(models.Model):
    """
    Ghi lại mọi thao tác cấp / thu hồi quyền trên từng nhân viên.
    Phục vụ audit trail và kiểm tra tuân thủ.
    """

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="access_logs",
        verbose_name="Nhân viên",
    )
    action = models.CharField(
        max_length=20,
        choices=AccessLogAction.choices,
        verbose_name="Hành động",
    )
    django_group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Nhóm quyền",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hrm_access_logs",
        verbose_name="Người thực hiện",
    )
    note = models.TextField(blank=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hrm_access_log"
        ordering = ["-created_at"]
        verbose_name = "Log phân quyền"
        verbose_name_plural = "Log phân quyền"

    def __str__(self):
        grp = self.django_group.name if self.django_group else "—"
        return f"[{self.action}] {self.employee} → {grp}"
