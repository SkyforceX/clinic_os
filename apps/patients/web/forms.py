from django import forms


class PatientCreateForm(forms.Form):
    company_id = forms.IntegerField(required=True)
    ma_bn = forms.CharField(label="Mã BN", max_length=20, required=True)
    ho_ten = forms.CharField(label="Họ tên", max_length=100, required=True)
    gioi_tinh = forms.CharField(label="Giới tính", max_length=10, required=True)
    ngay_sinh = forms.DateField(
        label="Ngày sinh",
        required=True,
        input_formats=["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    phone = forms.CharField(label="SĐT", max_length=15, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing_class + " form-control").strip()


class PatientUpdateForm(forms.Form):
    ma_bn = forms.CharField(label="Mã BN", max_length=20, required=True)
    ho_ten = forms.CharField(label="Họ tên", max_length=100, required=True)
    gioi_tinh = forms.CharField(label="Giới tính", max_length=10, required=True)
    ngay_sinh = forms.DateField(
        label="Ngày sinh",
        required=True,
        input_formats=["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    phone = forms.CharField(label="SĐT", max_length=15, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

        if instance is not None and not self.is_bound:
            self.initial.update(
                {
                    "ma_bn": instance.ma_bn,
                    "ho_ten": instance.ho_ten,
                    "gioi_tinh": instance.gioi_tinh,
                    "ngay_sinh": instance.ngay_sinh,
                    "phone": instance.phone,
                }
            )

        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing_class + " form-control").strip()