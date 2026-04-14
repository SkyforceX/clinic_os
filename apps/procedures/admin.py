from django.contrib import admin
from .models import Procedure, ProcedureStep, ProcedureAttachment


class ProcedureStepInline(admin.TabularInline):
    model = ProcedureStep
    extra = 0
    fields = ['title', 'parent', 'responsible', 'order', 'color']


class ProcedureAttachmentInline(admin.TabularInline):
    model = ProcedureAttachment
    extra = 0
    fields = ['name', 'file', 'file_type']


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'category', 'status', 'version', 'effective_date', 'created_by', 'created_at']
    list_filter = ['category', 'status']
    search_fields = ['title', 'code']
    inlines = [ProcedureStepInline, ProcedureAttachmentInline]
    readonly_fields = ['created_at', 'updated_at']
