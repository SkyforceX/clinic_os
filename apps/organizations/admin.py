from django.contrib import admin

from apps.organizations.models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "tax_code",
        "phone",
        "created_by",
        "created_at",
    )
    search_fields = (
        "name",
        "tax_code",
        "phone",
    )
    list_filter = (
        "created_at",
        "updated_at",
    )
    ordering = ("-id",)
    readonly_fields = (
        "id",
        "uuid",
        "created_at",
        "updated_at",
    )