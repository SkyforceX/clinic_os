from django.contrib import admin

from apps.clinical.models import DentalExamination, PathologyResult, ToothNotation


@admin.register(DentalExamination)
class DentalExaminationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "company",
        "tooth_loss_classification",
        "health_classification",
        "updated_at",
    )
    search_fields = (
        "patient__ma_bn",
        "patient__ho_ten",
        "company__name",
    )
    list_filter = (
        "tooth_loss_classification",
        "health_classification",
    )
    ordering = ("-updated_at", "-id")


@admin.register(ToothNotation)
class ToothNotationAdmin(admin.ModelAdmin):
    list_display = ("code", "description_vi", "description_en")
    search_fields = ("code", "description_vi", "description_en")
    ordering = ("code",)


@admin.register(PathologyResult)
class PathologyResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "location",
        "result_date",
        "evaluation",
        "updated_at",
    )
    search_fields = (
        "patient__ma_bn",
        "patient__ho_ten",
        "location",
        "manual_conclusion",
        "auto_extracted_conclusion",
    )
    list_filter = ("evaluation", "result_date")
    ordering = ("-result_date", "-id")