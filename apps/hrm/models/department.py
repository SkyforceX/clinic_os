from django.db import models


class Department(models.Model):
    """Phòng ban / Đơn vị."""

    name = models.CharField(max_length=150, unique=True, verbose_name="Tên phòng ban")
    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Mã phòng ban")
    description = models.TextField(blank=True, verbose_name="Mô tả")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Phòng ban cấp trên",
    )
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    display_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hrm_department"
        ordering = ["display_order", "name"]
        verbose_name = "Phòng ban"
        verbose_name_plural = "Phòng ban"

    def __str__(self):
        return self.name


class Position(models.Model):
    """Chức vụ / Chức danh."""

    name = models.CharField(max_length=150, unique=True, verbose_name="Tên chức vụ")
    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Mã chức vụ")
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions",
        verbose_name="Phòng ban",
    )
    level = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Cấp bậc",
        help_text="1 = nhân viên, 5 = trưởng phòng, 9 = giám đốc",
    )
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hrm_position"
        ordering = ["-level", "name"]
        verbose_name = "Chức vụ"
        verbose_name_plural = "Chức vụ"

    def __str__(self):
        return self.name
