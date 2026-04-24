from django.conf import settings
from django.db import models


class SystemGeneralSetting(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)

    default_am_slot_limit = models.PositiveIntegerField(default=100, verbose_name="Giới hạn slot mặc định buổi sáng")
    default_pm_slot_limit = models.PositiveIntegerField(default=100, verbose_name="Giới hạn slot mặc định buổi chiều")
    max_blood_location_per_day = models.PositiveIntegerField(
        default=0,
        verbose_name="Số địa điểm lấy máu tối đa trong 1 ngày",
        help_text="Nhập 0 để không giới hạn.",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_system_general_settings",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_system_general_setting"
        verbose_name = "Thiết lập chung hệ thống"
        verbose_name_plural = "Thiết lập chung hệ thống"

    def __str__(self):
        return "Thiết lập chung hệ thống"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            singleton_key=1,
            defaults={
                "default_am_slot_limit": 100,
                "default_pm_slot_limit": 100,
                "max_blood_location_per_day": 0,
            },
        )
        return obj


class PublicHoliday(models.Model):
    date = models.DateField(unique=True, verbose_name="Ngày nghỉ")
    name = models.CharField(max_length=100, blank=True, verbose_name="Tên ngày nghỉ")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_public_holiday"
        ordering = ["date"]
        verbose_name = "Ngày nghỉ lễ"
        verbose_name_plural = "Ngày nghỉ lễ"

    def __str__(self):
        return f"{self.date.strftime('%d/%m/%Y')} – {self.name or 'Ngày nghỉ'}"