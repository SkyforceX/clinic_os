from django import forms

from apps.catalogs.models import CheckupCategory, GroupCheckup


class GroupCheckupForm(forms.ModelForm):
    class Meta:
        model = GroupCheckup
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_name(self):
        name = (self.cleaned_data["name"] or "").strip()
        qs = GroupCheckup.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Nhóm này đã tồn tại.")
        return name


class CheckupCategoryForm(forms.ModelForm):
    class Meta:
        model = CheckupCategory
        fields = [
            "group_checkup",
            "item_name",
            "description",
            "price",
        ]
        widgets = {
            "group_checkup": forms.Select(attrs={"class": "form-select"}),
            "item_name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "price": forms.TextInput(attrs={"class": "form-control"}),
        }