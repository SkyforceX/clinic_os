from django import forms

from apps.core.models import SystemGeneralSetting


class SystemGeneralSettingForm(forms.ModelForm):
    class Meta:
        model = SystemGeneralSetting
        fields = ["default_am_slot_limit", "default_pm_slot_limit"]
        widgets = {
            "default_am_slot_limit": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "default_pm_slot_limit": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
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