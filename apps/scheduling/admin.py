from django.contrib import admin

from apps.scheduling.models import ScheduleSlot
from apps.booking.models import Appointment


def register_if_not_registered(model, admin_class):
    if model not in admin.site._registry:
        admin.site.register(model, admin_class)


class ScheduleSlotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contract",
        "date",
        "shift",
        "slot_type",
        "capacity",
        "booked_count",
        "status",
        "created_at",
    )
    list_filter = (
        "shift",
        "slot_type",
        "status",
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
        "schedule_slot",
        "assigned_staff",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "patient__ma_bn",
        "patient__ho_ten",
        "schedule_slot__contract__contract_number",
        "schedule_slot__contract__company__name",
    )
    ordering = ("-created_at",)

register_if_not_registered(ScheduleSlot, ScheduleSlotAdmin)
register_if_not_registered(Appointment, AppointmentAdmin)