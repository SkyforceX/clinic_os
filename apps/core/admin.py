from django.contrib import admin

from apps.core.models import SystemGeneralSetting


@admin.register(SystemGeneralSetting)
class SystemGeneralSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "default_am_slot_limit", "default_pm_slot_limit", "updated_by", "updated_at")
    readonly_fields = ("updated_at",)