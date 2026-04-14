from django.contrib import admin

from apps.reception.models import CheckInRecord


@admin.register(CheckInRecord)
class CheckInRecordAdmin(admin.ModelAdmin):
    list_display = [
        "snapshot_ma_bn", "snapshot_ho_ten", "snapshot_company_name",
        "exam_date", "status", "checked_in_at", "checked_out_at", "operator",
    ]
    list_filter  = ["status", "exam_date"]
    search_fields = ["snapshot_ma_bn", "snapshot_ho_ten", "snapshot_company_name"]
    date_hierarchy = "exam_date"
    readonly_fields = [
        "snapshot_ma_bn", "snapshot_ho_ten", "snapshot_gioi_tinh", "snapshot_ngay_sinh",
        "snapshot_company_name", "snapshot_exam_start", "snapshot_exam_end",
        "checked_in_at", "checked_out_at", "deferred_at", "created_at", "updated_at",
    ]
    raw_id_fields = ["patient", "company", "schedule_config", "operator"]
