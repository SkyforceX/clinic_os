from django.contrib import admin

from apps.booking.models import HealthContract, ContractServiceDetail, BloodCollectionInfo


@admin.register(HealthContract)
class HealthContractAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contract_number",
        "company",
        "employee_count",
        "start_date",
        "end_date",
        "is_approved",
        "is_terminated",
        "created_by",
        "created_at",
    )
    search_fields = (
        "contract_number",
        "company__name",
        "contact_person",
    )
    list_filter = (
        "is_approved",
        "is_terminated",
        "is_finished",
        "created_at",
    )
    ordering = ("-created_at",)


@admin.register(ContractServiceDetail)
class ContractServiceDetailAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contract",
        "item_name",
        "group_name",
        "for_male",
        "for_female_single",
        "for_female_family",
    )
    search_fields = (
        "contract__contract_number",
        "item_name",
        "group_name",
    )
    ordering = ("contract_id", "id")


@admin.register(BloodCollectionInfo)
class BloodCollectionInfoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contract",
        "collection_date",
        "location",
        "people_count",
        "staff_count",
    )
    search_fields = (
        "contract__contract_number",
        "location",
    )
    ordering = ("collection_date", "id")