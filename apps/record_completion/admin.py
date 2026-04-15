from django.contrib import admin

from apps.record_completion.models import RecordCompletion, RecordCompletionLog


class RecordCompletionLogInline(admin.TabularInline):
    model = RecordCompletionLog
    extra = 0
    readonly_fields = ("step", "actor", "note", "confirmed_at")
    can_delete = False


@admin.register(RecordCompletion)
class RecordCompletionAdmin(admin.ModelAdmin):
    list_display = (
        "checkin_record",
        "company",
        "current_step",
        "is_completed",
        "updated_at",
    )
    list_filter = ("is_completed", "current_step", "company")
    search_fields = (
        "checkin_record__snapshot_ma_bn",
        "checkin_record__snapshot_ho_ten",
        "company__name",
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = [RecordCompletionLogInline]


@admin.register(RecordCompletionLog)
class RecordCompletionLogAdmin(admin.ModelAdmin):
    list_display = ("record_completion", "step", "actor", "confirmed_at")
    list_filter = ("step",)
    readonly_fields = ("confirmed_at",)
