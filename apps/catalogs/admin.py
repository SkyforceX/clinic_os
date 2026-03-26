from django.contrib import admin

from apps.catalogs.models import CheckupCategory, GroupCheckup


@admin.register(GroupCheckup)
class GroupCheckupAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(CheckupCategory)
class CheckupCategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "item_name", "group_checkup", "price"]
    list_filter = ["group_checkup"]
    search_fields = ["item_name", "description"]