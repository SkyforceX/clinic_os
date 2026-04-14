"""
Thêm vào apps/hrm/admin.py:
"""
from django.contrib import admin
from apps.hrm.models.work_schedule import WorkSchedule, WorkScheduleLog


class WorkScheduleLogInline(admin.TabularInline):
    model = WorkScheduleLog
    extra = 0
    readonly_fields = ["actor", "old_shift", "new_shift", "note", "ip_address", "created_at"]
    can_delete = False


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ["employee", "schedule_date", "shift", "registered_by", "updated_at"]
    list_filter = ["shift", "schedule_date"]
    search_fields = ["employee__full_name", "employee__employee_code"]
    date_hierarchy = "schedule_date"
    raw_id_fields = ["employee", "registered_by"]
    inlines = [WorkScheduleLogInline]


@admin.register(WorkScheduleLog)
class WorkScheduleLogAdmin(admin.ModelAdmin):
    list_display = ["work_schedule", "actor", "old_shift", "new_shift", "created_at", "ip_address"]
    list_filter = ["new_shift", "created_at"]
    readonly_fields = ["work_schedule", "actor", "old_shift", "new_shift", "note", "ip_address", "created_at"]
    search_fields = ["work_schedule__employee__full_name"]
