from django.contrib import admin

from .models import Conversation, KnowledgeChunk, KnowledgeDocument, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "created_at")
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "created_at", "updated_at")
    list_filter = ("user",)
    search_fields = ("title", "user__username")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "short_content", "created_at")
    list_filter = ("role", "conversation__user")
    search_fields = ("content",)
    readonly_fields = ("created_at",)

    def short_content(self, obj):
        return obj.content[:80]

    short_content.short_description = "Nội dung"


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    extra = 0
    fields = ("chunk_index", "char_count", "content")
    readonly_fields = ("chunk_index", "char_count", "content")
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "source_type", "source_id", "title", "is_active", "last_indexed_at")
    list_filter = ("source_type", "is_active")
    search_fields = ("title", "content")
    readonly_fields = ("created_at", "last_indexed_at", "content_hash", "metadata")
    inlines = [KnowledgeChunkInline]


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "chunk_index", "char_count", "created_at")
    list_filter = ("document__source_type",)
    search_fields = ("content", "document__title")
    readonly_fields = ("created_at", "content_hash", "embedding", "metadata")
