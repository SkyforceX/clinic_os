# apps/quality/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditChoice(models.TextChoices):
    PASS_ = "PASS", "Đạt"
    FAIL_ = "FAIL", "Không đạt"
    NA    = "NA",   "Không áp dụng"


# apps/quality/models.py

class MedicalRecordAudit(TimeStampedModel):
    """
    BẢNG KIỂM TRA HỒ SƠ KHÁM NGOẠI TRÚ
    Dùng cho cá nhân kiểm tra 1 hồ sơ khám ngoại trú tại phòng khám đa khoa.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="outpatient_record_audits",
    )

    # Thông tin chung
    patient_name = models.CharField("Họ tên khách hàng", max_length=255)
    visit_date = models.DateField("Ngày khám", null=True, blank=True)
    patient_code = models.CharField(
        "Mã bệnh nhân / mã hồ sơ khám",
        max_length=50,
        blank=True,
    )
    clinic_room = models.CharField(
        "Phòng khám / chuyên khoa",
        max_length=100,
        blank=True,
    )
    doctor_name = models.CharField(
        "Bác sĩ khám",
        max_length=120,
        blank=True,
    )
    
    # ── I. THỦ TỤC HÀNH CHÍNH ─────────────────────────────────────────────
    q1_name_uppercase = models.CharField(
        "1. Họ tên người bệnh viết in hoa, có đánh dấu",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q2_no_erasure = models.CharField(
        "2. Ghi đầy đủ các mục, không sửa chữa/tẩy xóa/rách; sửa chữa đúng quy định "
        "(gạch ngang viết lại, không viết đè, có chữ ký nháy của người sửa)",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q3_documents_sorted = models.CharField(
        "3. Các loại giấy tờ, kết quả xét nghiệm được sắp xếp đúng nhóm, "
        "theo thứ tự thời gian trước - sau",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q4_page_numbered = models.CharField(
        "4. Có đánh số thứ tự trên HSBA",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q5_signatures = models.CharField(
        "5. Có đầy đủ chữ ký (bác sĩ, điều dưỡng, khách hàng) trên các trang cần ký",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q6_icd_code = models.CharField(
        "6. Ghi mã CD phù hợp với chẩn đoán",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    
    # ── II. CHẤT LƯỢNG CHẨN ĐOÁN ──────────────────────────────────────────
    q7_history_exam_full = models.CharField(
        "7. Hỏi tiền sử bệnh, tiền sử chi tiết; khám NB toàn diện, ghi bệnh án đầy đủ",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q8_tests_ordered = models.CharField(
        "8. Chỉ định đầy đủ các xét nghiệm lâm sàng",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q9_results_reviewed = models.CharField(
        "9. KQ lâm sàng, CLS được BS xem, xử trí, ký và ghi rõ họ tên",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q10_diagnosis_change_noted = models.CharField(
        "10. Thay đổi chẩn đoán, các thay đổi trên tờ điều trị có ghi rõ lý luận "
        "và cập nhật ngày giờ thay đổi",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q11_discharge_summary = models.CharField(
        "11. Khi ra viện có ghi rõ chẩn đoán xác định, chẩn đoán phân biệt; "
        "có tóm tắt HSBA điều trị",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    
    # ── III. CHẤT LƯỢNG ĐIỀU TRỊ - CHĂM SÓC ──────────────────────────────
    q12_progress_notes = models.CharField(
        "12. Ghi diễn tiến điều trị, chăm sóc hằng ngày theo trình tự thời gian (giờ - ngày); "
        "ký - ghi rõ họ tên BS/ĐD; NB nặng ghi diễn tiến theo ngày; kẻ ngang khi hết ngày",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q13_orders_appropriate = models.CharField(
        "13. Y lệnh điều trị hằng ngày phù hợp với chẩn đoán và diễn tiến bệnh, "
        "bám sát phác đồ điều trị chuẩn; chỉ định thuốc an toàn, hợp lý, hiệu quả",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q14_complex_case_noted = models.CharField(
        "14. Các trường hợp phức tạp có chỉ định HC, thực hiện HCCM, HC dùng thuốc "
        "chấm sao được ghi rõ ràng, chi tiết vào HSBA",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q15_vital_signs_chart = models.CharField(
        "15. Phiếu theo dõi chức năng sống ghi đầy đủ, chi tiết các mục: "
        "mạch (đỏ), nhiệt độ (xanh), huyết áp, BMI, nhịp thở,...",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q16_infusion_record = models.CharField(
        "16. Phiếu truyền dịch ghi đầy đủ giờ bắt đầu - kết thúc, tốc độ truyền, "
        "liều lượng, số lô, BS chỉ định, ĐD thực hiện; kẻ ngang khi hết ngày",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q17_blood_transfusion_record = models.CharField(
        "17. Phiếu truyền máu ghi đầy đủ các mục theo quy định an toàn truyền máu",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    q18_skin_test_record = models.CharField(
        "18. Phiếu thử phản ứng ghi đầy đủ thông tin, bằng chữ (âm tính, dương tính); "
        "ký và ghi rõ họ tên ĐD thực hiện, BS đọc kết quả",
        max_length=100,
        choices=AuditChoice.choices,
        null=True,
        blank=True,
    )
    
    # ── NHẬN XÉT CHUNG ────────────────────────────────────────────────────
    overall_comment = models.TextField(
        "Nhận xét chung / điểm cần cải tiến",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Kiểm tra hồ sơ khám ngoại trú"
        verbose_name_plural = "Kiểm tra hồ sơ khám ngoại trú"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Audit HSBA - {self.patient_name} ({self.visit_date})"

    # --- tính điểm checklist ---
    @classmethod
    def get_audit_field_names(cls):
        """
        Lấy danh sách các field câu hỏi audit (q1... q21)
        dựa trên việc có cùng choices với AuditChoice.
        """
        names = []
        for field in cls._meta.get_fields():
            if getattr(field, "choices", None) == AuditChoice.choices:
                names.append(field.name)
        return names

    def calc_score(self):
        """
        Trả về (so_pass, so_cau_tinh_diem, percent)
        - PASS  : 1 điểm
        - FAIL  : 0 điểm
        - NA    : loại khỏi mẫu số
        - blank: tính như FAIL (vẫn cộng vào mẫu số, không cộng điểm)
        """
        field_names = self.get_audit_field_names()
        total = 0
        passed = 0

        for name in field_names:
            val = getattr(self, name)

            if val == AuditChoice.NA:
                # Không áp dụng -> không tính vào mẫu số
                continue

            if val:  # có chọn PASS hoặc FAIL
                total += 1
                if val == AuditChoice.PASS_:
                    passed += 1
            else:
                # bỏ trống => coi như FAIL nhưng vẫn tính vào mẫu số
                total += 1

        if total == 0:
            return 0, 0, None

        percent = round(passed * 100 / total)
        return passed, total, percent

    @property
    def score_percent(self):
        """
        % điểm hồ sơ (0–100), hoặc None nếu không có câu nào được chấm.
        """
        return self.calc_score()[2]


class IncidentSeverity(models.TextChoices):
    NEAR_MISS = "NEAR_MISS", "Suýt xảy ra, không gây hậu quả"
    NO_HARM   = "NO_HARM",   "Đã xảy ra nhưng chưa gây hại"
    MINOR     = "MINOR",     "Nhẹ"
    MODERATE  = "MODERATE",  "Trung bình"
    SEVERE    = "SEVERE",    "Nặng"
    DEATH     = "DEATH",     "Tử vong"


class IncidentType(models.TextChoices):
    NEAR_MISS = "NEAR_MISS", "Suýt xảy ra"
    OCCURRED  = "OCCURRED",  "Đã xảy ra"


class IncidentName(models.TextChoices):
    # CLINICAL
    WRONG_DIAGNOSIS   = "wrong_diagnosis",   "Chẩn đoán sai / chậm chẩn đoán"
    WRONG_TREATMENT   = "wrong_treatment",   "Chỉ định điều trị / thủ thuật không phù hợp"
    TEST_ERROR        = "test_error",        "Sai sót xét nghiệm (lấy mẫu, nhãn, xử lý, trả kết quả)"
    PROCEDURE_ERROR   = "procedure_error",   "Sai sót kỹ thuật / thủ thuật"
    CLINICAL_OTHER    = "clinical_other",    "Khác (chuyên môn) – ghi rõ ở phần mô tả"

    # ADMIN
    BILLING_ERROR     = "billing_error",     "Sai sót thu ngân / thanh toán"
    INSURANCE_ERROR   = "insurance_error",   "Sai sót BHYT (hưởng sai, nhập sai thông tin, từ chối không đúng)"
    DATA_ENTRY_ERROR  = "data_entry_error",  "Nhập liệu hành chính sai / thiếu (họ tên, ngày sinh, địa chỉ...)"
    ADMIN_OTHER       = "admin_other",       "Khác (hành chính) – ghi rõ ở phần mô tả"

    # CSKH
    RUDE_BEHAVIOR     = "rude_behavior",     "Thái độ/giao tiếp chưa phù hợp"
    INFO_MISCOMM      = "info_miscomm",      "Truyền đạt thông tin sai / không đầy đủ cho khách hàng"
    CSKH_OTHER        = "cskh_other",        "Khác (CSKH) – ghi rõ ở phần mô tả"

    # IC
    ASEPTIC_BREAK     = "aseptic_break",     "Không tuân thủ vô khuẩn / vệ sinh tay"
    WASTE_ERROR       = "waste_error",       "Phân loại / xử lý rác y tế không đúng"
    IC_OTHER          = "ic_other",          "Khác (KSNK) – ghi rõ ở phần mô tả"

    # SAFETY
    FALL              = "fall",              "Ngã / suýt ngã trong cơ sở"
    DRUG_ALLERGY      = "drug_allergy",      "Dị ứng thuốc (đã biết / chưa được khai thác) "
    MED_ERROR         = "med_error",         "Sai sót dùng thuốc (nhầm liều, nhầm thuốc, nhầm người bệnh...)"
    SAFETY_OTHER      = "safety_other",      "Khác (an toàn NB) – ghi rõ ở phần mô tả"

    # EQUIP
    DEVICE_FAILURE    = "device_failure",    "Thiết bị hỏng / lỗi trong khi sử dụng"
    DEVICE_UNAVAIL    = "device_unavail",    "Thiết bị không sẵn sàng khi cần"
    EQUIP_OTHER       = "equip_other",       "Khác (trang thiết bị) – ghi rõ ở phần mô tả"

    # IT
    SYSTEM_DOWN       = "system_down",       "Phần mềm / hệ thống bị treo / không truy cập được"
    DATA_LOSS         = "data_loss",         "Mất dữ liệu / sai lệch dữ liệu trên hệ thống"
    INTEGRATION_ERROR = "integration_error", "Lỗi kết nối giữa các phần mềm (HIS, LIS, PACS…)"
    IT_OTHER          = "it_other",          "Khác (CNTT) – ghi rõ ở phần mô tả"


class IncidentAttachment(models.Model):
    incident = models.ForeignKey(
        "IncidentReport",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    image = models.ImageField(
        upload_to="quality/incidents/%Y/%m/%d/"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment #{self.pk} for incident {self.incident_id}"


class IncidentReport(TimeStampedModel):
    """
    Form báo cáo sự cố/rủi ro y khoa (cá nhân),
    thiết kế đơn giản, bám nội dung chính của Biên bản báo cáo sự cố.
    """

    # Ai báo cáo (sẽ gán từ request.user, nhưng cho phép lưu tên hiển thị)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="incident_reports"
    )
    reporter_name = models.CharField(
        "Người báo cáo (tự động lấy từ tài khoản, có thể chỉnh lại)",
        max_length=255,
        blank=True,
    )
    department = models.CharField(
        "Khoa/phòng báo cáo",
        max_length=255,
        blank=True,
    )

    # Thông tin người bệnh (không bắt buộc, vì có sự cố không liên quan NB)
    patient_name = models.CharField(
        "Họ tên bệnh nhân (nếu có)",
        max_length=255,
        blank=True,
    )
    patient_code = models.CharField(
        "Mã bệnh nhân / mã hồ sơ (nếu có)",
        max_length=50,
        blank=True,
    )

    # Thông tin sự cố
    incident_type = models.CharField(
        "Phân loại sự cố",
        max_length=100,
        choices=IncidentType.choices,
        default=IncidentType.OCCURRED,
    )

    incident_datetime = models.DateTimeField(
        "Thời điểm xảy ra",
        null=True,
        blank=True,
    )
    location = models.CharField(
        "Vị trí / khu vực xảy ra",
        max_length=255,
        blank=True,
    )
    related_policy = models.TextField(
        "Quy trình / chính sách liên quan (nếu có)",
        blank=True,
        help_text='Nếu chưa có quy trình, ghi rõ: "Chưa có quy trình/chính sách điều chỉnh".',
    )

    incident_name = models.CharField(
        "Mã tên sự cố",
        max_length=50,
        choices=IncidentName.choices,
        blank=True,
    )

    # Mô tả chi tiết: gom các mục diễn biến + cơ chế tìm nguyên nhân
    description = models.TextField(
        "Mô tả diễn biến / cơ chế sự cố",
        help_text=(
            "Mô tả từ khi bắt đầu, điều kiện, hoàn cảnh, diễn biến, "
            "các tác nhân tham gia, ai liên quan..."
        ),
    )

    # Hậu quả / nguy cơ
    consequence = models.TextField(
        "Hậu quả thực tế hoặc nguy cơ có thể xảy ra",
        blank=True,
        help_text=(
            "Nếu chưa xảy ra hậu quả ghi: 'Chưa xảy ra hậu quả' hoặc 'Suýt xảy ra hậu quả' "
            "và mô tả hậu quả có thể xảy ra."
        ),
    )

    severity = models.CharField(
        "Mức độ nghiêm trọng",
        max_length=100,
        choices=IncidentSeverity.choices,
    )

    # Xử trí tức thời + hành động tiếp theo
    immediate_action = models.TextField(
        "Hành động báo cáo & khắc phục tức thời",
        blank=True,
        help_text=(
            "Đã báo cáo cho ai, khi nào? Đã làm gì ngay sau khi phát hiện để giảm hậu quả?"
        ),
    )

    followup_action_quality = models.TextField(
        "Hành động/đề xuất của bộ phận QLCL",
        blank=True,
        help_text="Ví dụ: phân tích nguyên nhân gốc rễ, cảnh báo toàn viện, xây dựng quy trình...",
    )

    followup_action_department = models.TextField(
        "Hành động/đề xuất của khoa/phòng liên quan",
        blank=True,
        help_text="Các việc cần làm, người phụ trách, thời gian hoàn thành.",
    )

    training_plan = models.TextField(
        "Nhu cầu phổ biến / huấn luyện lại quy trình (nếu có)",
        blank=True,
    )

    other_corrective_actions = models.TextField(
        "Hành động khắc phục khác",
        blank=True,
    )

    attachment_note = models.TextField(
        "Hình ảnh / tài liệu / trích camera đính kèm",
        blank=True,
        help_text="Ghi đường dẫn file, vị trí lưu, hoặc mô tả tài liệu đính kèm.",
    )

    # Ẩn danh khi tổng hợp cho khoa/phòng
    is_anonymous_to_department = models.BooleanField(
        "Ẩn tên người báo cáo khi gửi báo cáo cho khoa/phòng",
        default=False,
    )

    class Meta:
        verbose_name = "Báo cáo sự cố y khoa"
        verbose_name_plural = "Báo cáo sự cố y khoa"
        ordering = ["-incident_datetime", "-created_at"]

    def __str__(self):
        return f"Sự cố: {self.get_incident_name_display() or 'Chưa ghi tên'} ({self.get_severity_display()})"
