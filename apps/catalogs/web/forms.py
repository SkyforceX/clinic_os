from django import forms
from django.db import transaction

from apps.catalogs.models import (
    CheckupCategory,
    CheckupPackageTemplate,
    CheckupPackageTemplateItem,
    GroupCheckup,
)


class GroupCheckupForm(forms.ModelForm):
    class Meta:
        model = GroupCheckup
        fields = ["name", "group_en", "display_order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "group_en": forms.TextInput(attrs={"class": "form-control"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        qs = GroupCheckup.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Nhóm khám này đã tồn tại.")
        return name


class CheckupCategoryForm(forms.ModelForm):
    class Meta:
        model = CheckupCategory
        fields = [
            "group_checkup",
            "subgroup_name",
            "display_order",
            "item_code",
            "item_name",
            "description",
            "list_price",
            "price_type",
            "price_male",
            "price_female_single",
            "price_female_family",
            "for_male",
            "for_female_single",
            "for_female_family",
            "note",
            "is_active",
        ]
        widgets = {
            "group_checkup": forms.Select(attrs={"class": "form-select"}),
            "subgroup_name": forms.TextInput(attrs={"class": "form-control"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "item_code": forms.TextInput(attrs={"class": "form-control"}),
            "item_name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "list_price": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 1}),
            "price_type": forms.Select(attrs={"class": "form-select"}),
            "price_male": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 1}),
            "price_female_single": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 1}),
            "price_female_family": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 1}),
            "for_male": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "for_female_single": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "for_female_family": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "note": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_item_name(self):
        return (self.cleaned_data.get("item_name") or "").strip()

    def clean_item_code(self):
        code = (self.cleaned_data.get("item_code") or "").strip()
        if not code:
            return None
        qs = CheckupCategory.objects.filter(item_code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Mã danh mục đã tồn tại.")
        return code


class CheckupPackageTemplateForm(forms.ModelForm):
    category_ids = forms.ModelMultipleChoiceField(
        queryset=CheckupCategory.objects.filter(is_active=True).select_related("group_checkup"),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="Danh mục khám",
    )

    class Meta:
        model = CheckupPackageTemplate
        fields = ["name", "description", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category_ids"].queryset = (
            CheckupCategory.objects.filter(is_active=True, group_checkup__is_active=True)
            .select_related("group_checkup")
            .order_by("group_checkup__display_order", "group_checkup__name", "display_order", "id")
        )

        if self.instance.pk:
            self.fields["category_ids"].initial = self.instance.categories.values_list("id", flat=True)

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()

    def grouped_categories(self):
        grouped = []
        current_group = None
        current_subgroup = None

        for category in self.fields["category_ids"].queryset:
            group_name = category.group_checkup.name
            subgroup_name = category.subgroup_name or ""

            if not grouped or current_group != group_name:
                grouped.append(
                    {
                        "group_name": group_name,
                        "subgroups": [],
                        "items": [],
                    }
                )
                current_group = group_name
                current_subgroup = None

            block = grouped[-1]
            if subgroup_name:
                if not block["subgroups"] or current_subgroup != subgroup_name:
                    block["subgroups"].append(
                        {
                            "subgroup_name": subgroup_name,
                            "items": [],
                        }
                    )
                    current_subgroup = subgroup_name
                block["subgroups"][-1]["items"].append(category)
            else:
                block["items"].append(category)

        return grouped

    @transaction.atomic
    def save(self, commit=True, created_by=None, updated_by=None):
        package = super().save(commit=False)

        if created_by and not package.pk:
            package.created_by = created_by
        if updated_by:
            package.updated_by = updated_by

        if commit:
            package.save()
            selected_categories = list(self.cleaned_data["category_ids"])
            package.items.all().delete()

            bulk_items = []
            for index, category in enumerate(selected_categories, start=1):
                bulk_items.append(
                    CheckupPackageTemplateItem(
                        package=package,
                        category=category,
                        display_order=index,
                    )
                )
            CheckupPackageTemplateItem.objects.bulk_create(bulk_items)

        return package