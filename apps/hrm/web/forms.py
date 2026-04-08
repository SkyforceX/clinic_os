from collections import defaultdict

from django import forms

from apps.hrm.models.department import Department, Position
from apps.hrm.models.employee import Employee, EmploymentType, GenderChoice


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "description", "parent", "is_active", "display_order"]
        widgets = {
            "name":        forms.TextInput(attrs={"class": "form-control"}),
            "code":        forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "parent":      forms.Select(attrs={"class": "form-select"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control"}),
        }


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["name", "code", "department", "level", "is_active"]
        widgets = {
            "name":       forms.TextInput(attrs={"class": "form-control"}),
            "code":       forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "level":      forms.NumberInput(attrs={"class": "form-control"}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            # Định danh
            "employee_code", "full_name", "gender", "date_of_birth",
            "phone", "email", "address",
            # Pháp lý
            "id_card_number", "id_card_issued_date", "id_card_issued_by",
            "tax_code", "social_insurance_code",
            "bank_account", "bank_name",
            # Công việc
            "department", "position", "direct_manager",
            "employment_type", "hire_date", "probation_end_date", "official_date",
            # Liên hệ khẩn cấp
            "emergency_contact_name", "emergency_contact_phone", "emergency_contact_rel",
            # Khác
            "note",
        ]
        widgets = {
            "employee_code": forms.TextInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "date_of_birth": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "id_card_number": forms.TextInput(attrs={"class": "form-control"}),
            "id_card_issued_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "id_card_issued_by": forms.TextInput(attrs={"class": "form-control"}),
            "tax_code": forms.TextInput(attrs={"class": "form-control"}),
            "social_insurance_code": forms.TextInput(attrs={"class": "form-control"}),
            "bank_account": forms.TextInput(attrs={"class": "form-control"}),
            "bank_name": forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "position": forms.Select(attrs={"class": "form-select"}),
            "direct_manager": forms.Select(attrs={"class": "form-select"}),
            "employment_type": forms.Select(attrs={"class": "form-select"}),
            "hire_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "probation_end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "official_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "emergency_contact_name": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_rel": forms.TextInput(attrs={"class": "form-control"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from apps.hrm.models.employee import EmployeeStatus

        active_departments = Department.objects.filter(is_active=True).order_by("display_order", "name")
        active_positions = Position.objects.filter(is_active=True).select_related("department").order_by("-level", "name")

        self.fields["department"].queryset = active_departments
        self.fields["direct_manager"].queryset = Employee.objects.filter(
            status__in=[EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION]
        ).order_by("full_name")

        self.fields["direct_manager"].empty_label = "— Không có —"
        self.fields["department"].empty_label = "— Chọn phòng ban —"
        self.fields["position"].empty_label = "— Chọn chức vụ —"

        selected_department_id = self.data.get("department") or getattr(self.instance, "department_id", None)

        if selected_department_id:
            self.fields["position"].queryset = active_positions.filter(department_id=selected_department_id)
        else:
            self.fields["position"].queryset = active_positions.none()

        position_choices_by_department = defaultdict(list)
        for pos in active_positions:
            if pos.department_id:
                position_choices_by_department[str(pos.department_id)].append({
                    "id": pos.pk,
                    "name": pos.name,
                })
        self.position_choices_by_department = dict(position_choices_by_department)

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get("department")
        position = cleaned_data.get("position")

        if position and not department:
            self.add_error("department", "Vui lòng chọn phòng ban trước khi chọn chức vụ.")

        if position and department and position.department_id != department.id:
            self.add_error("position", "Chức vụ không thuộc phòng ban đã chọn.")

        return cleaned_data


class TransferForm(forms.Form):
    """Form chuyển bộ phận / chức vụ."""

    new_position = forms.ModelChoiceField(
        queryset=Position.objects.filter(is_active=True).order_by("name"),
        label="Chức vụ mới",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    new_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by("name"),
        label="Phòng ban mới",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    note = forms.CharField(
        label="Lý do / Ghi chú",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class OffboardForm(forms.Form):
    """Form nghỉ việc."""

    resignation_date = forms.DateField(
        label="Ngày nghỉ việc",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    terminate = forms.BooleanField(
        label="Chấm dứt hợp đồng (không phải tự nghỉ)",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    reason = forms.CharField(
        label="Lý do",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
