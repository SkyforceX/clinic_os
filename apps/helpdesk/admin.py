from django.contrib import admin
from apps.helpdesk.models import Ticket, TicketMessage, TicketAttachment


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ("sender", "body", "is_system_event", "event_type", "created_at")
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("pk", "subject", "category", "priority", "status", "created_by", "assigned_to", "created_at")
    list_filter = ("status", "priority", "category")
    search_fields = ("subject", "created_by__username", "created_by__first_name")
    inlines = [TicketMessageInline]
    raw_id_fields = ("created_by", "assigned_to", "closed_by", "linked_task")
