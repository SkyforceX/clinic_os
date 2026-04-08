from django.contrib import admin

from apps.approvals.models import ApprovalLog, ApprovalRequest


class ApprovalLogInline(admin.TabularInline):
    model = ApprovalLog
    extra = 0
    readonly_fields = ("actor", "action", "note", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request_type",
        "document_label",
        "status",
        "requested_by",
        "requested_at",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = ("request_type", "status")
    search_fields = ("requested_by__username", "requested_by__first_name")
    readonly_fields = (
        "request_type",
        "status",
        "requested_by",
        "requested_at",
        "reviewed_by",
        "reviewed_at",
        "document_label",
    )
    inlines = [ApprovalLogInline]

    @admin.display(description="Tài liệu")
    def document_label(self, obj):
        return obj.document_label


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ("id", "approval_request", "action", "actor", "note", "created_at")
    list_filter = ("action",)
    readonly_fields = ("approval_request", "actor", "action", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
