from django import forms

from apps.organizations.models import Company


class CompanyForm(forms.Form):
    name = forms.CharField(
        label="Tên công ty",
        max_length=200,
        required=True,
    )
    address = forms.CharField(
        label="Địa chỉ",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    tax_code = forms.CharField(
        label="Mã số thuế",
        max_length=50,
        required=False,
    )
    phone = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=False,
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

        if instance is not None and not self.is_bound:
            self.initial.update(
                {
                    "name": instance.name,
                    "address": instance.address,
                    "tax_code": instance.tax_code,
                    "phone": instance.phone,
                }
            )

        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing_class + " form-control").strip()