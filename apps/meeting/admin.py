from django.contrib import admin

from apps.meeting.models import (
    DeptAssignment,
    MeetingCommitment,
    MeetingParticipant,
    MeetingSession,
    MeetingSignature,
    StaffShift,
)


class MeetingParticipantInline(admin.TabularInline):
    model = MeetingParticipant
    extra = 0
    fields = ("user", "department", "role", "can_edit", "joined_at")
    readonly_fields = ("joined_at",)


class DeptAssignmentInline(admin.TabularInline):
    model = DeptAssignment
    extra = 0
    fields = ("department", "lead_user", "confirmed", "confirmed_by", "confirmed_at")
    readonly_fields = ("confirmed_by", "confirmed_at")


class MeetingSignatureInline(admin.TabularInline):
    model = MeetingSignature
    extra = 0
    readonly_fields = ("user", "department", "role_label", "signed_at", "doc_hash", "ip_address")
    can_delete = False


@admin.register(MeetingSession)
class MeetingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "meeting_date", "company", "contract",
        "status", "current_step", "created_by", "created_at",
    )
    list_filter = ("status", "meeting_date")
    search_fields = ("title", "company__name", "contract__contract_number")
    readonly_fields = ("created_at", "updated_at", "closed_at", "closed_by")
    inlines = [MeetingParticipantInline, DeptAssignmentInline, MeetingSignatureInline]
    fieldsets = (
        ("Thông tin buổi họp", {
            "fields": ("title", "meeting_date", "meeting_time", "location", "note"),
        }),
        ("Liên kết nghiệp vụ", {
            "fields": ("contract", "company"),
        }),
        ("Trạng thái", {
            "fields": ("status", "current_step", "created_by", "closed_by", "closed_at"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


class StaffShiftInline(admin.TabularInline):
    model = StaffShift
    extra = 0
    fields = ("user", "role_in_day", "shift", "time_from", "time_to", "confirmed", "note")


@admin.register(DeptAssignment)
class DeptAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "session", "department", "lead_user",
        "confirmed", "confirmed_by", "confirmed_at",
    )
    list_filter = ("department", "confirmed")
    search_fields = ("session__title",)
    readonly_fields = ("confirmed_by", "confirmed_at", "created_at", "updated_at")
    inlines = [StaffShiftInline]


@admin.register(MeetingCommitment)
class MeetingCommitmentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "session", "dept_assignment",
        "assignee", "deadline", "status", "has_task",
    )
    list_filter = ("status",)
    search_fields = ("title", "session__title")
    readonly_fields = ("task", "created_at", "updated_at")

    @admin.display(boolean=True, description="Có Task?")
    def has_task(self, obj):
        return obj.task_id is not None


@admin.register(MeetingSignature)
class MeetingSignatureAdmin(admin.ModelAdmin):
    list_display = (
        "id", "session", "user", "department",
        "role_label", "signed_at", "ip_address",
    )
    readonly_fields = (
        "session", "user", "department", "role_label",
        "signed_at", "doc_hash", "ip_address", "user_agent",
    )
    search_fields = ("session__title", "user__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
