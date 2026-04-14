from django.contrib import admin

from apps.catalogs.models import (
    CheckupCategory,
    CheckupPackageTemplate,
    CheckupPackageTemplateItem,
    GroupCheckup,
)


@admin.register(GroupCheckup)
class GroupCheckupAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "group_en", "display_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "group_en"]
    ordering = ["display_order", "name"]


@admin.register(CheckupCategory)
class CheckupCategoryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "item_name",
        "group_checkup",
        "subgroup_name",
        "list_price",
        "price_type",
        "display_order",
        "is_active",
    ]
    list_filter = ["group_checkup", "price_type", "is_active"]
    search_fields = ["item_name", "item_code", "description", "subgroup_name", "note"]
    autocomplete_fields = ["group_checkup", "created_by", "updated_by"]
    ordering = ["group_checkup__display_order", "display_order", "id"]


class CheckupPackageTemplateItemInline(admin.TabularInline):
    model = CheckupPackageTemplateItem
    extra = 0
    autocomplete_fields = ["category"]


@admin.register(CheckupPackageTemplate)
class CheckupPackageTemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "created_by", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description", "created_by__username", "created_by__first_name", "created_by__last_name"]
    autocomplete_fields = ["created_by", "updated_by"]
    inlines = [CheckupPackageTemplateItemInline]