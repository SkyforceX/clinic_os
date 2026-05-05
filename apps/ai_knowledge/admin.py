from django.contrib import admin

from .models import AIKnowledgeChunk, AIKnowledgeSource


class AIKnowledgeChunkInline(admin.TabularInline):
    model = AIKnowledgeChunk
    extra = 0
    fields = (
        "chunk_index",
        "section_key",
        "section_title",
        "token_count",
        "content",
    )
    readonly_fields = fields
    can_delete = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AIKnowledgeSource)
class AIKnowledgeSourceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_type",
        "source_id",
        "title",
        "access_level",
        "status",
        "indexed_at",
    )
    list_filter = ("source_type", "access_level", "status", "locale")
    search_fields = ("title", "source_id", "metadata")
    readonly_fields = (
        "content_hash",
        "indexed_at",
        "last_error",
        "metadata",
        "created_at",
        "updated_at",
    )
    inlines = [AIKnowledgeChunkInline]


@admin.register(AIKnowledgeChunk)
class AIKnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_type",
        "source_id",
        "chunk_index",
        "section_key",
        "status",
        "updated_at",
    )
    list_filter = ("source_type", "access_level", "status", "locale")
    search_fields = ("title", "section_title", "content", "source_id")
    readonly_fields = (
        "embedding",
        "metadata",
        "created_at",
        "updated_at",
    )
