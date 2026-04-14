from django.conf import settings
from django.db import models


class SystemGeneralSetting(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)

    default_am_slot_limit = models.PositiveIntegerField(default=100, verbose_name="Giới hạn slot mặc định buổi sáng")
    default_pm_slot_limit = models.PositiveIntegerField(default=100, verbose_name="Giới hạn slot mặc định buổi chiều")

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
            },
        )
        return obj