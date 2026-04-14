from django.contrib import admin

from apps.scheduling.models import ContractScheduleConfig, ScheduleSlot


@admin.register(ContractScheduleConfig)
class ContractScheduleConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "quotation",
        "contract",
        "exam_start_date",
        "exam_end_date",
        "planned_employee_count",
        "am_capacity_limit",
        "pm_capacity_limit",
        "registered_by",
        "updated_at",
    )
    list_select_related = ("quotation", "contract", "registered_by")
    search_fields = (
        "quotation__id",
        "contract__id",
        "quotation__company__name",
        "quotation__company__company_name",
        "registered_by__username",
        "registered_by__first_name",
        "registered_by__last_name",
    )
    list_filter = (
        "exam_start_date",
        "exam_end_date",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("quotation", "registered_by")


@admin.register(ScheduleSlot)
class ScheduleSlotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date",
        "shift",
        "slot_type",
        "contract",
        "capacity",
        "booked_count",
        "remaining_capacity_display",
        "updated_at",
    )
    list_select_related = ("contract", "quotation")
    search_fields = (
        "contract__id",
    )
    list_filter = (
        "slot_type",
        "shift",
        "date",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("remaining_capacity_display", "created_at", "updated_at")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "contract",
                    "date",
                    "shift",
                    "slot_type",
                    "capacity",
                    "booked_count",
                    "remaining_capacity_display",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Còn lại")
    def remaining_capacity_display(self, obj):
        return obj.remaining_capacity