# apps/quality/forms.py
from django import forms
from .models import MedicalRecordAudit, IncidentReport, AuditChoice


class MedicalRecordAuditForm(forms.ModelForm):
    class Meta:
        model = MedicalRecordAudit
        exclude = ("created_by", "created_at", "updated_at")
        widgets = {
            "visit_date": forms.DateInput(
                attrs={
                    "type": "date",  # Browser datepicker
                    "class": "form-control",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Duyệt field model để biết field nào có choices = AuditChoice
        for name, field in self.fields.items():
            model_field = self._meta.model._meta.get_field(name)

            if getattr(model_field, "choices", None) == AuditChoice.choices:
                field.widget = forms.RadioSelect(choices=AuditChoice.choices)

        # Placeholder đẹp hơn
        self.fields["patient_name"].widget.attrs.update(
            {"placeholder": "Ví dụ: NGUYỄN VĂN A"}
        )
        self.fields["patient_code"].widget.attrs.update(
            {"placeholder": "Mã BN/HSBA (nếu có)"}
        )
        self.fields["overall_comment"].widget.attrs.update(
            {"rows": 3, "style": "width: 100%;", "placeholder": "Nhận xét chung, đề xuất cải tiến..."}
        )



class IncidentReportForm(forms.ModelForm):
    POLICY_GROUP_CHOICES = [
        ("CLINICAL", "Sự cố chuyên môn (kỹ thuật, thủ thuật, xét nghiệm, chẩn đoán...)"),
        ("ADMIN", "Sự cố hành chính (thu ngân, BHYT, nhập liệu sai...)"),
        ("CSKH", "Sự cố giao tiếp – CSKH"),
        ("IC", "Sự cố vệ sinh – kiểm soát nhiễm khuẩn"),
        ("SAFETY", "Sự cố an toàn người bệnh (té ngã, dị ứng thuốc, sai sót điều trị…)"),
        ("EQUIP", "Sự cố trang thiết bị"),
        ("IT", "Sự cố CNTT / phần mềm"),
    ]
    # 🔹 Map giống bên JS (value, label)
    INCIDENT_NAME_CHOICES = {
        "CLINICAL": [
            ("wrong_diagnosis", "Chẩn đoán sai / chậm chẩn đoán"),
            ("wrong_treatment", "Chỉ định điều trị / thủ thuật không phù hợp"),
            ("test_error", "Sai sót xét nghiệm (lấy mẫu, nhãn, xử lý, trả kết quả)"),
            ("procedure_error", "Sai sót kỹ thuật / thủ thuật"),
            ("clinical_other", "Khác (chuyên môn) – ghi rõ ở phần mô tả"),
        ],
        "ADMIN": [
            ("billing_error", "Sai sót thu ngân / thanh toán"),
            ("bhyt_error", "Sai thông tin / hồ sơ BHYT"),
            ("data_entry", "Nhập liệu sai thông tin hành chính"),
            ("admin_other", "Khác (hành chính) – ghi rõ ở phần mô tả"),
        ],
        "CSKH": [
            ("impolite", "Thái độ / giao tiếp không phù hợp"),
            ("poor_info", "Hướng dẫn không rõ ràng / gây hiểu nhầm"),
            ("cskh_other", "Khác (CSKH) – ghi rõ ở phần mô tả"),
        ],
        "IC": [
            ("hand_hygiene", "Không tuân thủ vệ sinh tay"),
            ("ppe", "Không sử dụng bảo hộ / PPE đúng quy định"),
            ("env_cleaning", "Vệ sinh môi trường, buồng khám, dụng cụ không đảm bảo"),
            ("waste_management", "Phân loại / xử lý rác thải y tế không đúng"),
            ("ic_other", "Khác (kiểm soát NK) – ghi rõ ở phần mô tả"),
        ],
        "SAFETY": [
            ("fall", "Người bệnh té ngã / chấn thương"),
            ("drug_allergy", "Phản ứng dị ứng / ADR thuốc"),
            ("med_error", "Sai sót dùng thuốc (loại, liều, đường dùng, thời gian)"),
            ("id_error", "Nhầm lẫn người bệnh / nhầm hồ sơ"),
            ("safety_other", "Khác (an toàn NB) – ghi rõ ở phần mô tả"),
        ],
        "EQUIP": [
            ("device_failure", "Thiết bị hỏng / lỗi trong khi sử dụng"),
            ("device_unavail", "Thiết bị không sẵn sàng khi cần"),
            ("equip_other", "Khác (trang thiết bị) – ghi rõ ở phần mô tả"),
        ],
        "IT": [
            ("system_down", "Phần mềm / hệ thống bị treo / không truy cập được"),
            ("data_loss", "Mất dữ liệu / sai lệch dữ liệu trên hệ thống"),
            ("integration_error", "Lỗi kết nối giữa các phần mềm (HIS, LIS, PACS…)"),
            ("it_other", "Khác (CNTT) – ghi rõ ở phần mô tả"),
        ],
    }
    class Meta:
        model = IncidentReport
        exclude = ("reported_by",)  # set trong view
        widgets = {
            "incident_datetime": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": (
                        "Mô tả rõ: sự việc bắt đầu thế nào, điều kiện, hoàn cảnh, "
                        "diễn biến, ai tham gia, cơ chế hình thành sự cố..."
                    ),
                }
            ),
            "consequence": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": (
                        "Hậu quả thực tế (hoặc nguy cơ): tổn thương NB, thiệt hại tài sản, "
                        "ảnh hưởng uy tín, hoặc 'chưa xảy ra hậu quả'..."
                    ),
                }
            ),
            "immediate_action": forms.Textarea(
                attrs={
                    "rows": 2,
                    "class": "form-control",
                }
            ),
            "followup_action_quality": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
            "followup_action_department": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
            "training_plan": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
            "other_corrective_actions": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
            "attachment_note": forms.Textarea(
                attrs={"rows": 2, "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # ========= Helper: tất cả incident choices (gộp tất cả nhóm, dùng khi không xác định group) =========
        all_incident_choices = []
        for group_choices in self.INCIDENT_NAME_CHOICES.values():
            for choice in group_choices:
                if choice not in all_incident_choices:
                    all_incident_choices.append(choice)

        # ========= 1) Lấy giá trị hiện tại từ instance / POST =========
        if self.is_bound:
            # POST: ưu tiên data từ form
            policy_value = (self.data.get("related_policy") or "").strip().upper()
            incident_value = (self.data.get("incident_name") or "").strip()
        else:
            # GET: lấy từ instance (hoặc initial)
            policy_value = (
                (self.initial.get("related_policy") or getattr(self.instance, "related_policy", "") or "")
                .strip()
                .upper()
            )
            incident_value = (
                self.initial.get("incident_name")
                or getattr(self.instance, "incident_name", "")
                or ""
            ).strip()

        # ========= 2) Build field select 1: related_policy =========
        self.fields["related_policy"] = forms.ChoiceField(
            choices=[("", "---------")] + self.POLICY_GROUP_CHOICES,
            label="Nhóm quy trình / loại sự cố",
            required=True,
        )
        if policy_value and not self.is_bound:
            self.fields["related_policy"].initial = policy_value

        # ========= 3) Xác định danh sách incident_name theo group =========
        if policy_value and policy_value in self.INCIDENT_NAME_CHOICES:
            incident_choices = list(self.INCIDENT_NAME_CHOICES[policy_value])
        else:
            # Nếu chưa chọn nhóm hoặc dữ liệu cũ không khớp group -> cho xem tất cả
            incident_choices = list(all_incident_choices)

        # Nếu đang edit và incident_value không nằm trong list -> chèn thêm để hiển thị được
        if incident_value:
            if not any(v == incident_value for v, _ in incident_choices):
                incident_choices = [(incident_value, incident_value)] + incident_choices

        # ========= 4) Build field select 2: incident_name =========
        self.fields["incident_name"] = forms.ChoiceField(
            choices=[("", "---------")] + incident_choices,
            label="Tên sự cố cụ thể",
            required=True,
        )
        if incident_value and not self.is_bound:
            self.fields["incident_name"].initial = incident_value

        # ========= 5) Class CSS cho 2 select =========
        for name in ["related_policy", "incident_name"]:
            self.fields[name].widget.attrs.update({"class": "form-select"})

        # ========= 6) Auto điền reporter_name khi tạo mới =========
        if user and not self.instance.pk:
            full_name = getattr(user, "get_full_name", None)
            if callable(full_name):
                full_name = user.get_full_name()
            if full_name:
                self.fields["reporter_name"].initial = full_name

        # ========= 7) Thêm class form-control cho các field còn lại =========
        for name, field in self.fields.items():
            if name in self.Meta.widgets:
                continue
            if name in ["related_policy", "incident_name"]:
                # đã gán form-select ở trên
                continue
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css_class + " form-control").strip()