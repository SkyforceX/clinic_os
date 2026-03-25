from django.contrib import admin

from apps.scheduling.models import Appointment, BloodCollectionPlan, ScheduleSlot


def register_if_not_registered(model, admin_class):
    if model not in admin.site._registry:
        admin.site.register(model, admin_class)


class ScheduleSlotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contract",
        "date",
        "shift",
        "registered_am",
        "registered_pm",
        "limit_am",
        "limit_pm",
        "created_at",
    )
    list_filter = (
        "shift",
        "date",
        "created_at",
    )
    search_fields = (
        "contract__contract_number",
        "contract__company__name",
    )
    ordering = ("date", "shift", "id")


class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "schedule",
        "assigned_staff",
        "created_at",
    )
    list_filter = (
        "created_at",
        "updated_at",
    )
    search_fields = (
        "patient__ma_bn",
        "patient__ho_ten",
        "schedule__contract__contract_number",
        "schedule__contract__company__name",
    )
    ordering = ("-created_at",)


class BloodCollectionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contract",
        "collection_date",
        "location",
        "people_count",
        "staff_count",
    )
    list_filter = ("collection_date",)
    search_fields = (
        "contract__contract_number",
        "contract__company__name",
        "location",
    )
    ordering = ("collection_date", "id")


register_if_not_registered(ScheduleSlot, ScheduleSlotAdmin)
register_if_not_registered(Appointment, AppointmentAdmin)
register_if_not_registered(BloodCollectionPlan, BloodCollectionPlanAdmin)