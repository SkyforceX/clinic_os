from django.contrib import admin

from apps.patients.models import Patient, PatientCompanyHistory


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ma_bn",
        "ho_ten",
        "gioi_tinh",
        "ngay_sinh",
        "company",
        "phone",
        "created_at",
    )
    search_fields = (
        "ma_bn",
        "ho_ten",
        "phone",
        "email",
    )
    list_filter = (
        "gioi_tinh",
        "company",
        "created_at",
        "updated_at",
    )
    ordering = ("id",)
    readonly_fields = (
        "id",
        "uuid",
        "created_at",
        "updated_at",
    )


@admin.register(PatientCompanyHistory)
class PatientCompanyHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "company",
        "from_date",
        "to_date",
        "created_at",
    )
    search_fields = (
        "patient__ma_bn",
        "patient__ho_ten",
        "company__name",
    )
    list_filter = (
        "company",
        "from_date",
        "to_date",
    )
    ordering = ("-from_date", "-created_at")