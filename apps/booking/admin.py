from django.contrib import admin
from django.utils.html import format_html

from .models import HisAppointmentPushLog


@admin.register(HisAppointmentPushLog)
class HisAppointmentPushLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "appointment_link",
        "status_badge",
        "attempt",
        "http_status_code",
        "endpoint_short",
        "error_short",
        "created_at",
        "pushed_at",
    )
    list_filter = ("status", "attempt", "created_at")
    search_fields = (
        "appointment__patient__ma_bn",
        "appointment__patient__ho_ten",
        "appointment__his_patient_sync__his_patient_code",
        "error",
        "endpoint",
    )
    readonly_fields = (
        "appointment", "status", "attempt", "endpoint",
        "payload", "http_status_code", "response_data", "response_text",
        "error", "skipped_reason", "created_at", "pushed_at",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    def appointment_link(self, obj):
        if not obj.appointment_id:
            return "—"
        return format_html(
            '<a href="/admin/booking/appointment/{}/change/">Appt #{}</a>',
            obj.appointment_id,
            obj.appointment_id,
        )
    appointment_link.short_description = "Lịch hẹn"

    def status_badge(self, obj):
        colors = {
            "SUCCESS": "#16a34a",
            "FAILED":  "#dc2626",
            "QUEUED":  "#d97706",
            "SKIPPED": "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:white;background:{};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Trạng thái"

    def endpoint_short(self, obj):
        if not obj.endpoint:
            return "—"
        return obj.endpoint[:60] + ("…" if len(obj.endpoint) > 60 else "")
    endpoint_short.short_description = "Endpoint"

    def error_short(self, obj):
        if not obj.error:
            return "—"
        return obj.error[:80] + ("…" if len(obj.error) > 80 else "")
    error_short.short_description = "Lỗi"
