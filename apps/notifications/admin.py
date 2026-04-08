from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ("id", "recipient", "event_type", "level", "title", "is_read", "created_at")
    list_filter   = ("level", "event_type", "is_read")
    search_fields = ("recipient__username", "title", "body")
    readonly_fields = ("recipient", "event_type", "level", "title", "body",
                       "url", "meta", "created_at")
    actions = ["mark_all_read"]

    @admin.action(description="Đánh dấu đã đọc")
    def mark_all_read(self, request, queryset):
        queryset.update(is_read=True)
