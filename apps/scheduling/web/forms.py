from django import forms

from apps.core.models import PublicHoliday, SystemGeneralSetting
from apps.scheduling.models import SpecialExamCategory


class SystemGeneralSettingForm(forms.ModelForm):
    class Meta:
        model = SystemGeneralSetting
        fields = ["default_am_slot_limit", "default_pm_slot_limit", "max_blood_location_per_day"]
        widgets = {
            "default_am_slot_limit": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "default_pm_slot_limit": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "max_blood_location_per_day": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
        }

    def clean_default_am_slot_limit(self):
        value = int(self.cleaned_data["default_am_slot_limit"] or 0)
        if value <= 0:
            raise forms.ValidationError("Giới hạn slot sáng phải lớn hơn 0.")
        return value

    def clean_default_pm_slot_limit(self):
        value = int(self.cleaned_data["default_pm_slot_limit"] or 0)
        if value <= 0:
            raise forms.ValidationError("Giới hạn slot chiều phải lớn hơn 0.")
        return value


class PublicHolidayForm(forms.ModelForm):
    class Meta:
        model = PublicHoliday
        fields = ["date", "name"]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ví dụ: Tết Nguyên Đán"}
            ),
        }


class SpecialExamCategoryForm(forms.ModelForm):
    class Meta:
        model = SpecialExamCategory
        fields = ["name", "description", "display_order", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ví dụ: Siêu âm tim"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }