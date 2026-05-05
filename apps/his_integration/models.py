import json
import re
from functools import lru_cache
from pathlib import Path

from django.db import models
from django.utils import timezone
from apps.hrm.models import Employee


class HisSyncState(models.Model):
    source = models.CharField(max_length=50, unique=True, db_index=True)
    last_auto_id = models.BigIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'his_integration_sync_state'
        verbose_name = 'Trạng thái đồng bộ HIS'
        verbose_name_plural = 'Trạng thái đồng bộ HIS'


class HisPatientSync(models.Model):
    GENDER_CHOICES = [
        ('0', 'Nam'),
        ('1', 'Nữ'),
        ('2', 'Khác'),
    ]
    
    his_patient_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Mã BN HIS')
    his_patient_auto_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    
    full_name = models.CharField(max_length=200, verbose_name='Họ tên')
    birth_date_text = models.CharField(max_length=20, blank=True, verbose_name='Ngày/tháng sinh')
    birth_year = models.IntegerField(null=True, blank=True, verbose_name='Năm sinh')
    gender_code = models.CharField(max_length=10, blank=True, choices=GENDER_CHOICES, verbose_name='Giới tính')
    
    phone = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='SĐT')
    phone_enabled = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, verbose_name='Email')
    
    national_id = models.CharField(max_length=20, blank=True, db_index=True, verbose_name='CMND/CCCD')
    national_id_issue_date = models.DateField(null=True, blank=True, verbose_name='Ngày cấp')
    national_id_issue_place = models.CharField(max_length=200, blank=True, verbose_name='Nơi cấp')
    national_id_issue_place_code = models.CharField(max_length=20, blank=True)
    
    passport_number = models.CharField(max_length=50, blank=True, verbose_name='Số hộ chiếu')
    passport_issue_place = models.CharField(max_length=200, blank=True)
    passport_issue_date = models.DateField(null=True, blank=True)
    
    ethnicity_code = models.CharField(max_length=20, blank=True, verbose_name='Mã dân tộc')
    occupation_code = models.CharField(max_length=20, blank=True, verbose_name='Mã nghề nghiệp')
    country_code = models.CharField(max_length=20, blank=True)
    province_code = models.CharField(max_length=20, blank=True, verbose_name='Mã tỉnh/TP')
    district_code = models.CharField(max_length=20, blank=True, verbose_name='Mã quận/huyện')
    ward_code = models.CharField(max_length=20, blank=True, verbose_name='Mã xã/phường')
    hamlet_address = models.TextField(blank=True, verbose_name='Thôn/ấp')
    address = models.TextField(blank=True, verbose_name='Địa chỉ')
    full_address_label = models.TextField(blank=True)
    
    old_province_code = models.CharField(max_length=20, blank=True)
    old_district_code = models.CharField(max_length=20, blank=True)
    old_ward_code = models.CharField(max_length=20, blank=True)
    old_address = models.TextField(blank=True)
    household_address = models.TextField(blank=True, verbose_name='Hộ khẩu TT')
    hometown = models.CharField(max_length=200, blank=True, verbose_name='Quê quán')
    
    work_place = models.CharField(max_length=200, blank=True, verbose_name='Nơi làm việc')
    employee_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nhân viên')
    rank_code = models.CharField(max_length=50, blank=True)
    unit_code = models.CharField(max_length=50, blank=True)
    
    emergency_contact_name = models.CharField(max_length=200, blank=True, verbose_name='Người liên hệ khẩn cấp')
    emergency_contact_phone = models.CharField(max_length=50, blank=True, verbose_name='SĐT người liên hệ')
    
    fingerprint_1 = models.BinaryField(null=True, blank=True)
    fingerprint_2 = models.BinaryField(null=True, blank=True)
    fingerprint_3 = models.BinaryField(null=True, blank=True)
    patient_image = models.BinaryField(null=True, blank=True)
    patient_signature = models.BinaryField(null=True, blank=True)
    relative_signature = models.BinaryField(null=True, blank=True)
    
    outpatient_treatment_flag = models.BooleanField(null=True, blank=True)
    completed_treatment_flag = models.BooleanField(null=True, blank=True)
    receive_online_result = models.BooleanField(default=False)
    vip_flag = models.BooleanField(default=False, verbose_name='VIP')
    kiosk_checkin_flag = models.BooleanField(null=True, blank=True)
    
    client_source_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nguồn khách')
    vip_card_code = models.CharField(max_length=50, blank=True)
    
    enlist_date = models.DateField(null=True, blank=True, verbose_name='Ngày nhập ngũ')
    discharge_date = models.DateField(null=True, blank=True, verbose_name='Ngày xuất ngũ')
    reserve_date = models.DateField(null=True, blank=True, verbose_name='Ngày tái ngũ')
    
    family_status_code = models.CharField(max_length=20, blank=True)
    age_in_months = models.IntegerField(null=True, blank=True)
    age_in_weeks = models.IntegerField(null=True, blank=True)
    age_in_hours = models.IntegerField(null=True, blank=True)
    
    chronic_disease_flag = models.BooleanField(null=True, blank=True, verbose_name='Bệnh mãn tính')
    long_term_treatment_flag = models.BooleanField(null=True, blank=True, verbose_name='Điều trị dài ngày')
    
    server_source = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True, verbose_name='Ghi chú')
    warning_note = models.TextField(blank=True, verbose_name='Lưu ý')
    password_raw = models.CharField(max_length=200, blank=True)
    
    stt = models.IntegerField(null=True, blank=True)
    his_sysdate = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True, verbose_name='Lần đồng bộ cuối')
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        db_table = 'his_integration_patient_sync'
        verbose_name = 'Bệnh nhân HIS'
        verbose_name_plural = 'Bệnh nhân HIS'
        indexes = [
            models.Index(fields=['his_patient_code']),
            models.Index(fields=['phone']),
            models.Index(fields=['national_id']),
            models.Index(fields=['last_synced_at']),
        ]
    
    @property
    def birth_date_display(self) -> str:
        """Trả về ngày sinh dạng DD/MM/YYYY, fallback về năm nếu thiếu DD/MM."""
        from datetime import datetime
        text = (self.birth_date_text or "").strip()
        year = self.birth_year

        for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
            except (ValueError, AttributeError):
                continue

        if text and year:
            for fmt in ("%d/%m", "%d-%m"):
                try:
                    partial = datetime.strptime(text, fmt)
                    return f"{partial.strftime('%d/%m')}/{year}"
                except (ValueError, AttributeError):
                    continue

        return str(year) if year else ""

    @property
    def ma_bn(self) -> str:
        return self.his_patient_code

    @property
    def ho_ten(self) -> str:
        return self.full_name

    @property
    def ngay_sinh(self):
        from apps.his_integration.selectors import get_his_patient_birth_date
        return get_his_patient_birth_date(self)

    @property
    def gioi_tinh(self) -> str:
        mapping = {"0": "Nam", "1": "Nữ", "2": "Khác", "M": "Nam", "F": "Nữ"}
        return mapping.get((self.gender_code or "").strip().upper(), self.gender_code or "")

    def __str__(self):
        return f"{self.his_patient_code} - {self.full_name}"


class HisPatientTypeSync(models.Model):
    his_patient_type_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Mã đối tượng HIS')
    patient_type_name = models.CharField(max_length=200, verbose_name='Tên đối tượng')
    description = models.TextField(blank=True, verbose_name='Mô tả')
    has_card = models.BooleanField(null=True, blank=True)
    
    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'his_integration_patient_type_sync'
        verbose_name = 'Đối tượng BN HIS'
        verbose_name_plural = 'Đối tượng BN HIS'
    
    def __str__(self):
        return f"{self.his_patient_type_code} - {self.patient_type_name}"


class HisCorporatePackageSync(models.Model):
    his_package_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Mã gói khám HIS')
    package_name = models.CharField(max_length=300, verbose_name='Tên gói khám')
    
    company_name = models.CharField(max_length=300, verbose_name='Tên công ty')
    company_address = models.TextField(blank=True, verbose_name='Địa chỉ công ty')
    company_tax_code = models.CharField(max_length=50, blank=True, verbose_name='Mã số thuế')
    
    exam_type = models.IntegerField(null=True, blank=True, verbose_name='Hình thức khám')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='% Giảm giá')
    
    valid_from = models.DateField(null=True, blank=True, verbose_name='Hiệu lực từ ngày')
    valid_to = models.DateField(null=True, blank=True, verbose_name='Hiệu lực đến ngày')
    total_patients = models.IntegerField(default=0, verbose_name='Số lượng BN')
    
    client_source_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nguồn khách')
    exam_year = models.IntegerField(null=True, blank=True, verbose_name='Năm khám')
    exam_round = models.IntegerField(null=True, blank=True, verbose_name='Đợt khám')
    exam_purpose = models.TextField(blank=True, verbose_name='Mục đích khám')
    
    contract_number = models.CharField(max_length=100, blank=True, verbose_name='Số hợp đồng')
    contract_date = models.DateField(null=True, blank=True, verbose_name='Ngày ký HĐ')
    concluding_doctor = models.CharField(max_length=100, blank=True, verbose_name='BS kết luận')
    
    conclusion = models.TextField(blank=True, verbose_name='Kết luận')
    package_group = models.CharField(max_length=100, blank=True, verbose_name='Nhóm đoàn')
    
    image_data = models.BinaryField(null=True, blank=True)
    server_source = models.CharField(max_length=50, blank=True)
    
    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    contract = models.ForeignKey(
        'contract.Contract',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='his_packages',
        verbose_name='Hợp đồng clinic_os'
    )
    organization = models.ForeignKey(
        'organizations.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='his_packages',
        verbose_name='Công ty clinic_os'
    )
    
    class Meta:
        db_table = 'his_integration_corporate_package_sync'
        verbose_name = 'Gói khám đoàn HIS'
        verbose_name_plural = 'Gói khám đoàn HIS'
        indexes = [
            models.Index(fields=['his_package_code']),
            models.Index(fields=['company_name']),
            models.Index(fields=['valid_from', 'valid_to']),
        ]
    
    def __str__(self):
        return f"{self.his_package_code} - {self.package_name}"


class HisExamRecordSync(models.Model):
    his_record_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Mã hồ sơ HIS')
    his_record_auto_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    his_admission_number = models.CharField(max_length=50, blank=True)
    
    patient_sync = models.ForeignKey(
        HisPatientSync,
        on_delete=models.CASCADE,
        related_name='exam_records',
        verbose_name='Bệnh nhân HIS'
    )
    package_sync = models.ForeignKey(
        HisCorporatePackageSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_records',
        verbose_name='Gói khám HIS'
    )
    patient_type_sync = models.ForeignKey(
        HisPatientTypeSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_records',
        verbose_name='Đối tượng BN HIS'
    )
    
    exam_date = models.DateField(null=True, blank=True, verbose_name='Ngày khám')
    exam_datetime = models.DateTimeField(null=True, blank=True, verbose_name='Ngày giờ khám')
    discharge_date = models.DateTimeField(null=True, blank=True, verbose_name='Ngày ra viện')
    
    status_code = models.IntegerField(null=True, blank=True, verbose_name='Trạng thái phiếu')
    payment_status = models.BooleanField(default=False, verbose_name='Đã thanh toán')
    
    reason_for_visit = models.TextField(blank=True, verbose_name='Lý do vào khám')
    diagnosis = models.TextField(blank=True, verbose_name='Chẩn đoán')
    conclusion = models.TextField(blank=True, verbose_name='Kết luận')
    
    icd10_code_1 = models.CharField(max_length=50, blank=True, verbose_name='Mã bệnh 1')
    icd10_code_2 = models.CharField(max_length=50, blank=True)
    icd10_code_3 = models.CharField(max_length=50, blank=True)
    icd10_main = models.CharField(max_length=50, blank=True, verbose_name='Mã bệnh chính')
    
    icd10_desc_1 = models.TextField(blank=True)
    icd10_desc_2 = models.TextField(blank=True)
    icd10_desc_3 = models.TextField(blank=True)
    
    vital_signs = models.JSONField(default=dict, blank=True, verbose_name='Sinh hiệu')
    clinical_exam = models.JSONField(default=dict, blank=True, verbose_name='Khám lâm sàng')
    lab_results = models.JSONField(default=dict, blank=True, verbose_name='Kết quả XN')
    prescriptions = models.JSONField(default=list, blank=True, verbose_name='Đơn thuốc')
    
    medical_history = models.TextField(blank=True, verbose_name='Tiền sử bệnh')
    family_history = models.TextField(blank=True, verbose_name='Tiền sử gia đình')
    disease_process = models.TextField(blank=True, verbose_name='Quá trình bệnh lý')
    
    treatment_method = models.TextField(blank=True, verbose_name='Cách xử lý')
    treatment_result = models.IntegerField(null=True, blank=True, verbose_name='Kết quả điều trị')
    
    doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Mã BS')
    doctor_name = models.CharField(max_length=200, blank=True, verbose_name='Tên BS')
    receptionist_code = models.CharField(max_length=50, blank=True, verbose_name='Mã tiếp nhận')
    
    department_position = models.CharField(max_length=200, blank=True, verbose_name='Bộ phận')
    job_title = models.CharField(max_length=200, blank=True, verbose_name='Chức vụ')
    
    corporate_status = models.IntegerField(default=0, verbose_name='TT chỉ định đoàn')
    corporate_arrival_status = models.IntegerField(default=0, verbose_name='TT hồ sơ đoàn')
    number_issued_status = models.IntegerField(default=0, verbose_name='TT phát số')
    corporate_order_number = models.IntegerField(null=True, blank=True, verbose_name='STT đoàn')
    corporate_barcode = models.CharField(max_length=100, blank=True)
    
    checkin_state = models.IntegerField(null=True, blank=True, verbose_name='Trạng thái check-in')
    
    health_classification = models.CharField(max_length=50, blank=True, verbose_name='Loại sức khỏe')
    health_prediction = models.TextField(blank=True, verbose_name='Dự báo SK')
    prevention_advice = models.TextField(blank=True, verbose_name='Phòng ngừa')
    consultation_conclusion = models.TextField(blank=True, verbose_name='KL & tư vấn')
    
    stt = models.IntegerField(null=True, blank=True)
    server_source = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True, verbose_name='Ghi chú')
    internal_note = models.TextField(blank=True, verbose_name='Lưu ý nội bộ')
    
    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    is_complete = models.BooleanField(default=False, db_index=True, verbose_name='Hoàn thành')
    missing_fields = models.JSONField(default=list, blank=True, verbose_name='Trường thiếu')
    validation_errors = models.JSONField(default=list, blank=True, verbose_name='Lỗi validation')
    
    class Meta:
        db_table = 'his_integration_exam_record_sync'
        verbose_name = 'Hồ sơ khám HIS'
        verbose_name_plural = 'Hồ sơ khám HIS'
        indexes = [
            models.Index(fields=['his_record_code']),
            models.Index(fields=['exam_date']),
            models.Index(fields=['is_complete']),
            models.Index(fields=['checkin_state']),
        ]
    
    def __str__(self):
        return f"{self.his_record_code} - {self.patient_sync.full_name}"


class HisDiagnosticImagingSync(models.Model):
    his_imaging_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Ma CDHA HIS')
    his_admission_number = models.CharField(max_length=50, blank=True)

    exam_record_sync = models.ForeignKey(
        HisExamRecordSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnostic_imaging_records',
        verbose_name='Ho so kham HIS'
    )
    patient_sync = models.ForeignKey(
        HisPatientSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnostic_imaging_records',
        verbose_name='Benh nhan HIS'
    )

    sequence_number = models.IntegerField(null=True, blank=True, verbose_name='STT')
    daily_sequence_number = models.IntegerField(null=True, blank=True, verbose_name='STT ngay')
    internal_sequence_number = models.IntegerField(null=True, blank=True, verbose_name='STT noi bo')

    exam_date = models.DateTimeField(null=True, blank=True, verbose_name='Ngay vao kham')
    ordered_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngay gio y lenh')
    performed_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngay thuc hien')
    performed_dispatch_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngay thuc hien dieu phoi')
    machine_received_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngay vao may')
    dispatch_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngay dieu phoi')
    his_sysdate = models.DateTimeField(null=True, blank=True)

    request_text = models.TextField(blank=True, verbose_name='Yeu cau')
    note = models.TextField(blank=True, verbose_name='Ghi chu')
    result_rtf = models.TextField(blank=True, verbose_name='Ket qua RTF')
    result_text = models.TextField(blank=True, verbose_name='Ket qua text')
    result_html = models.TextField(blank=True, verbose_name='Ket qua HTML')
    conclusion = models.TextField(blank=True, verbose_name='Ket luan')

    ordering_doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Ma BS chi dinh')
    imaging_doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Ma BS CDHA')
    performing_doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Ma BS thuc hien')
    user_code = models.CharField(max_length=50, blank=True, verbose_name='Ma nguoi dung CDHA')

    status_code = models.IntegerField(null=True, blank=True, verbose_name='Trang thai phieu')
    queue_status = models.IntegerField(null=True, blank=True, verbose_name='Trang thai cho')
    internal_status = models.IntegerField(null=True, blank=True, verbose_name='Trang thai noi bo')
    pacs_status = models.IntegerField(null=True, blank=True, verbose_name='Trang thai PACS')

    clinical_department_code = models.CharField(max_length=50, blank=True, verbose_name='Ma khoa CLS')
    clinical_room_code = models.CharField(max_length=50, blank=True, verbose_name='Ma phong CLS')
    service_code = models.CharField(max_length=50, blank=True, verbose_name='Ma dich vu')
    exam_department_code = models.CharField(max_length=50, blank=True, verbose_name='Ma khoa kham')
    exam_room_code = models.CharField(max_length=50, blank=True, verbose_name='Ma phong kham')
    machine_code = models.CharField(max_length=50, blank=True, verbose_name='Ma may CLS')
    result_template_code = models.CharField(max_length=100, blank=True, verbose_name='Ma phieu ket qua')

    image_1 = models.TextField(blank=True)
    image_2 = models.TextField(blank=True)
    image_3 = models.TextField(blank=True)
    image_4 = models.TextField(blank=True)
    sid_to_pacs = models.CharField(max_length=100, blank=True)
    printed_images = models.CharField(max_length=255, blank=True)

    size_13_18 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    size_18_24 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    size_24_30 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    size_30_40 = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_voluntary = models.BooleanField(null=True, blank=True)
    priority = models.IntegerField(null=True, blank=True)
    is_skipped = models.BooleanField(null=True, blank=True)
    pushed_to_pacs = models.BooleanField(null=True, blank=True)
    is_locked = models.BooleanField(null=True, blank=True)
    auto_unlock = models.BooleanField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    locked_by_code = models.CharField(max_length=50, blank=True)

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_diagnostic_imaging_sync'
        verbose_name = 'Chan doan hinh anh HIS'
        verbose_name_plural = 'Chan doan hinh anh HIS'
        indexes = [
            models.Index(fields=['his_imaging_code']),
            models.Index(fields=['exam_record_sync']),
            models.Index(fields=['patient_sync']),
            models.Index(fields=['service_code', 'performed_at']),
        ]

    def __str__(self):
        return self.his_imaging_code


class HisDiagnosticImagingItemSync(models.Model):
    imaging_sync = models.ForeignKey(
        HisDiagnosticImagingSync,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Phieu CDHA HIS'
    )
    his_imaging_detail_auto_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name='ID chi tiet CDHA HIS'
    )

    service_item_code = models.CharField(max_length=50, blank=True, verbose_name='Ma chi tieu')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Don gia')
    collected_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Da thu tien')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='So luong')
    performed_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='So luong thuc hien')

    note = models.TextField(blank=True, verbose_name='Ghi chu')
    his_sysdate = models.DateTimeField(null=True, blank=True)
    is_package_service = models.BooleanField(null=True, blank=True, verbose_name='Tron goi')
    send_status = models.IntegerField(null=True, blank=True, verbose_name='Trang thai gui')
    pushed_to_pacs = models.BooleanField(null=True, blank=True, verbose_name='Da day PACS')
    qr_code = models.TextField(blank=True, verbose_name='QR Code')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_diagnostic_imaging_item_sync'
        verbose_name = 'Chi tiet chan doan hinh anh HIS'
        verbose_name_plural = 'Chi tiet chan doan hinh anh HIS'
        indexes = [
            models.Index(fields=['his_imaging_detail_auto_id']),
            models.Index(fields=['service_item_code']),
        ]

    def __str__(self):
        return f"{self.imaging_sync_id} - {self.service_item_code}"


# ---------------------------------------------------------------------------
# dbo.DMDichVuChiTiet — Danh mục dịch vụ / chỉ tiêu CLS
# ---------------------------------------------------------------------------
class HisServiceCatalogSync(models.Model):
    """Danh mục dịch vụ chi tiết (khám bệnh + CLS) từ HIS."""

    service_item_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Mã chỉ tiêu')
    service_item_name = models.CharField(max_length=300, verbose_name='Tên chỉ tiêu')
    service_item_name_order = models.CharField(max_length=300, blank=True, verbose_name='Tên chỉ định')

    service_group_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã nhóm DV')
    service_sub_group_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nhóm DM chi tiết')
    report_group_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nhóm báo cáo')
    result_print_group_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nhóm in KQ XN')
    common_group_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nhóm DV chung')

    unit = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị')
    result_unit = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị trả KQ')
    sort_order = models.IntegerField(default=0, verbose_name='Số thứ tự')
    sort_order_tb = models.IntegerField(default=0, verbose_name='STT TB')

    normal_value = models.CharField(max_length=500, blank=True, verbose_name='Trị số bình thường')
    normal_value_male = models.CharField(max_length=500, blank=True, verbose_name='TSBT Nam')
    normal_value_female = models.CharField(max_length=500, blank=True, verbose_name='TSBT Nữ')
    result_template_code = models.CharField(max_length=100, blank=True, verbose_name='Mã KQ mẫu')

    is_high_tech = models.BooleanField(default=False, verbose_name='Kỹ thuật cao')
    is_insurance_excluded = models.BooleanField(default=False, verbose_name='BH không thanh toán')
    is_no_discount = models.BooleanField(default=False, verbose_name='Không giảm giá')
    is_no_sample = models.BooleanField(default=False, verbose_name='Không lấy mẫu')
    is_pay_once = models.BooleanField(default=False, verbose_name='Thanh toán một lần')
    is_at_bed = models.BooleanField(default=False, verbose_name='Thực hiện tại giường')
    is_batch_perform = models.BooleanField(default=False, verbose_name='Thực hiện gộp')
    is_out_of_bh = models.BooleanField(default=False, verbose_name='Giường ngoài BH')

    lis_code = models.CharField(max_length=100, blank=True, verbose_name='Mã LIS')
    lis_machine_code = models.CharField(max_length=100, blank=True, verbose_name='Mã máy LIS')
    cls_machine_code = models.CharField(max_length=100, blank=True, verbose_name='Mã máy CLS')
    surgery_group_id = models.IntegerField(default=0, verbose_name='ID nhóm phẫu thuật')
    byt_code = models.CharField(max_length=50, blank=True, verbose_name='Mã BYT')
    bh_code = models.CharField(max_length=50, blank=True, verbose_name='Mã BH')
    syt_code = models.CharField(max_length=50, blank=True, verbose_name='Mã SYT')
    common_item_code = models.CharField(max_length=50, blank=True, verbose_name='Mã chỉ tiêu chung')
    common_index_code = models.CharField(max_length=50, blank=True, verbose_name='Mã chỉ số chung')
    xn_index_code = models.CharField(max_length=50, blank=True, verbose_name='Mã chỉ số XN')
    xml_group_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nhóm XML')
    surgery_type_code = models.CharField(max_length=10, blank=True, verbose_name='Mã loại PTTT')

    expected_duration = models.IntegerField(default=0, verbose_name='TG thực hiện dự kiến (phút)')
    radiation_count = models.IntegerField(default=0, verbose_name='Số lần phát tia')

    is_active_use = models.BooleanField(default=True, verbose_name='Đang sử dụng')
    is_visible = models.BooleanField(default=True, verbose_name='Hiển thị')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_service_catalog_sync'
        verbose_name = 'Danh mục dịch vụ HIS'
        verbose_name_plural = 'Danh mục dịch vụ HIS'
        indexes = [
            models.Index(fields=['service_item_code']),
            models.Index(fields=['service_group_code']),
        ]

    def __str__(self):
        return f"{self.service_item_code} - {self.service_item_name}"


# ---------------------------------------------------------------------------
# dbo.DanhSachDichVuDinhNghiaTruocKhamTheoGoi — DV định nghĩa theo gói đoàn
# ---------------------------------------------------------------------------
class HisPackageServiceSync(models.Model):
    """Danh sách dịch vụ/CLS định nghĩa trước cho từng gói khám đoàn."""

    his_order_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Mã đơn')

    # Denormalized: giữ lại mã gốc ngay cả khi package chưa sync hoặc bị xóa
    his_package_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã gói HIS')

    package_sync = models.ForeignKey(
        HisCorporatePackageSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_services',
        verbose_name='Gói khám đoàn HIS',
        to_field='his_package_code',
    )
    service_catalog = models.ForeignKey(
        HisServiceCatalogSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_service_lines',
        verbose_name='Dịch vụ HIS',
        to_field='service_item_code',
    )
    service_item_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã chỉ tiêu')

    unit = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name='Số lượng')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Đơn giá')
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Thành tiền')
    room_code = models.CharField(max_length=50, blank=True, verbose_name='Mã phòng')

    is_outside_package = models.BooleanField(default=False, verbose_name='Ngoài gói')
    is_selected = models.BooleanField(default=True, verbose_name='Được chọn chỉ định')
    created_by = models.CharField(max_length=100, blank=True, verbose_name='Người tạo')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_package_service_sync'
        verbose_name = 'Dịch vụ theo gói đoàn HIS'
        verbose_name_plural = 'Dịch vụ theo gói đoàn HIS'
        indexes = [
            models.Index(fields=['package_sync', 'is_outside_package']),
            models.Index(fields=['service_item_code']),
        ]

    def __str__(self):
        return f"{self.his_order_code} — {self.service_item_code}"


# ---------------------------------------------------------------------------
# dbo.PhieuThamDoChucNang — Phiếu thăm dò chức năng (TDCN / nội soi / ECG)
# ---------------------------------------------------------------------------
class HisFunctionalTestSync(models.Model):
    """Phiếu thăm dò chức năng từ HIS (nội soi, ECG, siêu âm có giao diện riêng...)."""

    his_ft_code = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Mã TDCN HIS')
    his_admission_number = models.CharField(max_length=50, blank=True)

    exam_record_sync = models.ForeignKey(
        HisExamRecordSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='functional_test_records',
        verbose_name='Hồ sơ khám HIS',
        to_field='his_record_code',
    )
    patient_sync = models.ForeignKey(
        HisPatientSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='functional_test_records',
        verbose_name='Bệnh nhân HIS',
        to_field='his_patient_code',
    )

    sequence_number = models.IntegerField(null=True, blank=True, verbose_name='STT')
    daily_sequence_number = models.IntegerField(null=True, blank=True, verbose_name='STT ngày')

    exam_date = models.DateTimeField(null=True, blank=True, verbose_name='Ngày vào khám')
    ordered_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày giờ y lệnh')
    performed_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày thực hiện')
    machine_received_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày vào máy')
    dispatch_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày điều phối')
    his_sysdate = models.DateTimeField(null=True, blank=True)

    request_text = models.TextField(blank=True, verbose_name='Yêu cầu')
    note = models.TextField(blank=True, verbose_name='Ghi chú')
    result_text = models.TextField(blank=True, verbose_name='Kết quả text')
    result_html = models.TextField(blank=True, verbose_name='Kết quả HTML')
    conclusion = models.TextField(blank=True, verbose_name='Kết luận')

    ordering_doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Mã BS chỉ định')
    ft_doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Mã BS TDCN')
    performing_doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Mã BS thực hiện')
    user_code = models.CharField(max_length=50, blank=True, verbose_name='Mã người dùng TDCN')

    status_code = models.IntegerField(null=True, blank=True, verbose_name='Trạng thái phiếu')
    queue_status = models.IntegerField(null=True, blank=True, verbose_name='Trạng thái chờ')
    internal_status = models.IntegerField(null=True, blank=True, verbose_name='Trạng thái nội bộ')
    pacs_status = models.IntegerField(null=True, blank=True, verbose_name='Trạng thái PACS')

    clinical_department_code = models.CharField(max_length=50, blank=True, verbose_name='Mã khoa CLS')
    clinical_room_code = models.CharField(max_length=50, blank=True, verbose_name='Mã phòng CLS')
    service_code = models.CharField(max_length=50, blank=True, verbose_name='Mã dịch vụ')
    exam_department_code = models.CharField(max_length=50, blank=True, verbose_name='Mã khoa khám')
    exam_room_code = models.CharField(max_length=50, blank=True, verbose_name='Mã phòng khám')
    machine_code = models.CharField(max_length=50, blank=True, verbose_name='Mã máy CLS')
    result_template_code = models.CharField(max_length=100, blank=True, verbose_name='Mã phiếu KQ')
    sid_to_pacs = models.CharField(max_length=100, blank=True)

    has_anesthesia = models.BooleanField(null=True, blank=True, verbose_name='Có gây mê')
    hp_test = models.BooleanField(null=True, blank=True, verbose_name='Test nhanh HP')
    hp_test_time = models.CharField(max_length=50, blank=True, verbose_name='Thời gian test HP')
    is_voluntary = models.BooleanField(null=True, blank=True, verbose_name='Tự nguyện')
    priority = models.IntegerField(null=True, blank=True, verbose_name='Ưu tiên')
    is_skipped = models.BooleanField(null=True, blank=True, verbose_name='Bỏ qua')
    pushed_to_pacs = models.BooleanField(null=True, blank=True, verbose_name='Đã đẩy PACS')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_functional_test_sync'
        verbose_name = 'Phiếu TDCN HIS'
        verbose_name_plural = 'Phiếu TDCN HIS'
        indexes = [
            models.Index(fields=['his_ft_code']),
            models.Index(fields=['exam_record_sync']),
            models.Index(fields=['patient_sync']),
            models.Index(fields=['service_code', 'performed_at']),
        ]

    def __str__(self):
        return self.his_ft_code


# ---------------------------------------------------------------------------
# dbo.PhieuThamDoChucNangChiTiet — Chi tiết phiếu TDCN
# ---------------------------------------------------------------------------
class HisFunctionalTestItemSync(models.Model):
    """Chi tiết dịch vụ/chỉ tiêu trong một phiếu TDCN."""

    ft_sync = models.ForeignKey(
        HisFunctionalTestSync,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Phiếu TDCN HIS',
    )
    service_catalog = models.ForeignKey(
        HisServiceCatalogSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ft_item_lines',
        verbose_name='Dịch vụ HIS',
        to_field='service_item_code',
    )
    service_item_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã chỉ tiêu')

    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Đơn giá')
    collected_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Đã thu tiền')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name='Số lượng')
    performed_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='SL thực hiện')

    note = models.TextField(blank=True, verbose_name='Ghi chú')
    his_sysdate = models.DateTimeField(null=True, blank=True)
    is_package_service = models.BooleanField(null=True, blank=True, verbose_name='Trọn gói')
    send_status = models.IntegerField(null=True, blank=True, verbose_name='Trạng thái gửi')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_functional_test_item_sync'
        verbose_name = 'Chi tiết phiếu TDCN HIS'
        verbose_name_plural = 'Chi tiết phiếu TDCN HIS'
        unique_together = [('ft_sync', 'service_item_code')]
        indexes = [
            models.Index(fields=['ft_sync', 'service_item_code']),
        ]

    def __str__(self):
        return f"{self.ft_sync_id} - {self.service_item_code}"


# ---------------------------------------------------------------------------
# dbo.PhieuKhamBenhChiTiet — Chi tiết dịch vụ khám bệnh trong hồ sơ
# ---------------------------------------------------------------------------
class HisExamServiceItemSync(models.Model):
    """
    Chi tiết dịch vụ/chỉ tiêu trong phiếu khám bệnh (KB...).
    MaKhamBenh là mã phiếu KB trong HIS; nhiều phiếu KB có thể thuộc 1 MaHoSo.
    """

    ma_kham_benh = models.CharField(max_length=50, db_index=True, verbose_name='Mã phiếu KB HIS')

    exam_record_sync = models.ForeignKey(
        HisExamRecordSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_service_items',
        verbose_name='Hồ sơ khám HIS',
        to_field='his_record_code',
    )
    service_catalog = models.ForeignKey(
        HisServiceCatalogSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_service_lines',
        verbose_name='Dịch vụ HIS',
        to_field='service_item_code',
    )
    service_item_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã chỉ tiêu')

    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Đơn giá')
    collected_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Đã thu tiền')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Số lượng')
    his_sysdate = models.DateTimeField(null=True, blank=True)
    is_package_service = models.BooleanField(default=False, verbose_name='Trọn gói')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_exam_service_item_sync'
        verbose_name = 'Chi tiết dịch vụ KB HIS'
        verbose_name_plural = 'Chi tiết dịch vụ KB HIS'
        unique_together = [('ma_kham_benh', 'service_item_code')]
        indexes = [
            models.Index(fields=['ma_kham_benh']),
            models.Index(fields=['exam_record_sync', 'service_item_code']),
        ]

    def __str__(self):
        return f"{self.ma_kham_benh} - {self.service_item_code}"


# ---------------------------------------------------------------------------
# dbo.DanhSachLichHen — Lịch hẹn bệnh nhân
# ---------------------------------------------------------------------------
class HisAppointmentSync(models.Model):
    """Lịch hẹn bệnh nhân từ HIS."""

    his_appointment_id = models.BigIntegerField(unique=True, db_index=True, verbose_name='ID lịch hẹn HIS')

    patient_sync = models.ForeignKey(
        HisPatientSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='his_appointments',
        verbose_name='Bệnh nhân HIS',
        to_field='his_patient_code',
    )
    his_patient_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã BN HIS')

    exam_record_sync = models.ForeignKey(
        HisExamRecordSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='his_appointments',
        verbose_name='Hồ sơ khám HIS',
        to_field='his_record_code',
    )
    his_record_code = models.CharField(max_length=50, blank=True, verbose_name='Mã hồ sơ HIS')

    doctor_code = models.CharField(max_length=50, blank=True, verbose_name='Mã bác sĩ')
    department_code = models.CharField(max_length=50, blank=True, verbose_name='Mã khoa')
    content = models.TextField(blank=True, verbose_name='Nội dung hẹn')

    start_datetime = models.DateTimeField(null=True, blank=True, verbose_name='Ngày bắt đầu')
    end_datetime = models.DateTimeField(null=True, blank=True, verbose_name='Ngày kết thúc')
    appointment_date = models.DateTimeField(null=True, blank=True, verbose_name='Ngày tháng')

    status = models.IntegerField(default=0, verbose_name='Trạng thái')
    appointment_type = models.IntegerField(default=0, verbose_name='Loại lịch hẹn')
    created_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày tạo')
    created_by = models.CharField(max_length=100, blank=True, verbose_name='Người tạo')
    sms_sent = models.BooleanField(default=False, verbose_name='Đã gửi SMS')
    message_id = models.BigIntegerField(null=True, blank=True, verbose_name='ID tin nhắn')
    web_booking_id = models.BigIntegerField(null=True, blank=True, verbose_name='ID lịch hẹn web')
    booking_code = models.CharField(max_length=100, blank=True, verbose_name='Booking code')
    service_order_code = models.CharField(max_length=100, blank=True, verbose_name='Mã phiếu DV')
    client_source_code = models.CharField(max_length=50, blank=True, verbose_name='Mã nguồn khách')

    # Thông tin BN tại thời điểm đặt lịch (denormalized)
    patient_name = models.CharField(max_length=200, blank=True, verbose_name='Tên BN')
    birth_year = models.IntegerField(null=True, blank=True, verbose_name='Năm sinh')
    phone = models.CharField(max_length=50, blank=True, verbose_name='SĐT')
    address = models.TextField(blank=True, verbose_name='Địa chỉ')
    gender_code = models.CharField(max_length=10, blank=True, verbose_name='Mã giới tính')
    email = models.EmailField(blank=True, verbose_name='Email')
    national_id = models.CharField(max_length=20, blank=True, verbose_name='CCCD')
    reason_for_visit = models.TextField(blank=True, verbose_name='Lý do vào khám')
    note = models.TextField(blank=True, verbose_name='Ghi chú')
    internal_note = models.TextField(blank=True, verbose_name='Lưu ý nội bộ')
    outsold_reason = models.CharField(max_length=200, blank=True, verbose_name='Lý do outsold')
    days_count = models.IntegerField(null=True, blank=True, verbose_name='Số ngày')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_appointment_sync'
        verbose_name = 'Lịch hẹn HIS'
        verbose_name_plural = 'Lịch hẹn HIS'
        indexes = [
            models.Index(fields=['his_appointment_id']),
            models.Index(fields=['his_patient_code']),
            models.Index(fields=['start_datetime']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Lịch hẹn #{self.his_appointment_id} - {self.patient_name}"


# ---------------------------------------------------------------------------
# MeInvoice — Hóa đơn điện tử
# ---------------------------------------------------------------------------
class HisInvoiceSync(models.Model):
    """Hóa đơn điện tử phát hành qua HIS."""

    PUBLISH_STATUS_CHOICES = [
        (0, 'Chưa phát hành'),
        (1, 'Đã phát hành'),
        (2, 'Đã hủy'),
    ]

    his_invoice_ref_id = models.CharField(max_length=100, unique=True, db_index=True, verbose_name='RefID HIS')
    ref_type = models.IntegerField(default=0, verbose_name='Loại chứng từ')

    patient_sync = models.ForeignKey(
        HisPatientSync,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name='Bệnh nhân HIS',
        to_field='his_patient_code',
    )
    his_patient_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã BN HIS')

    invoice_date = models.DateField(null=True, blank=True, verbose_name='Ngày hóa đơn')
    customer_name = models.CharField(max_length=300, blank=True, verbose_name='Tên khách hàng')
    customer_tax_code = models.CharField(max_length=50, blank=True, verbose_name='MST')
    customer_email = models.EmailField(blank=True, verbose_name='Email KH')
    customer_address = models.TextField(blank=True, verbose_name='Địa chỉ KH')
    customer_bank_account = models.CharField(max_length=100, blank=True)
    customer_bank_name = models.CharField(max_length=200, blank=True)

    receiver_mobile = models.CharField(max_length=50, blank=True, verbose_name='SĐT nhận HĐ')
    receiver_email = models.EmailField(blank=True, verbose_name='Email nhận HĐ')
    payment_method = models.CharField(max_length=50, blank=True, verbose_name='Phương thức TT')
    currency = models.CharField(max_length=10, default='VND', verbose_name='Đơn vị tiền tệ')
    exchange_rate = models.CharField(max_length=20, default='1')

    total_amount = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Tổng tiền')
    total_sale_amount = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Tổng tiền sau CK')
    total_discount_amount = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Tổng CK')
    total_vat_amount = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Tổng VAT')

    publish_status = models.IntegerField(
        choices=PUBLISH_STATUS_CHOICES, default=0, verbose_name='Trạng thái phát hành'
    )
    inv_template_no = models.CharField(max_length=20, blank=True, verbose_name='Mẫu số HĐ')
    inv_series = models.CharField(max_length=20, blank=True, verbose_name='Ký hiệu HĐ')
    inv_no = models.CharField(max_length=50, blank=True, verbose_name='Số HĐ')
    is_deleted = models.BooleanField(default=False, verbose_name='Đã hủy')

    # Trường tùy chỉnh HIS
    cashier_code = models.CharField(max_length=100, blank=True, verbose_name='Mã thu ngân')
    cashier_name = models.CharField(max_length=200, blank=True, verbose_name='Tên thu ngân')
    his_record_codes = models.TextField(blank=True, verbose_name='Mã hồ sơ HIS')
    patient_type_code = models.CharField(max_length=50, blank=True, verbose_name='Mã đối tượng BN')
    transaction_id = models.CharField(max_length=100, blank=True)
    einvoice_mapping_id = models.CharField(max_length=100, blank=True)

    created_date = models.DateTimeField(null=True, blank=True, verbose_name='Ngày tạo')
    modified_date = models.DateTimeField(null=True, blank=True, verbose_name='Ngày sửa')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_invoice_sync'
        verbose_name = 'Hóa đơn HIS'
        verbose_name_plural = 'Hóa đơn HIS'
        indexes = [
            models.Index(fields=['his_invoice_ref_id']),
            models.Index(fields=['his_patient_code']),
            models.Index(fields=['invoice_date']),
            models.Index(fields=['publish_status']),
        ]

    def __str__(self):
        return f"HĐ {self.inv_no or self.his_invoice_ref_id[:8]} - {self.customer_name}"


# ---------------------------------------------------------------------------
# MeInvoiceRequestDetail — Chi tiết hóa đơn
# ---------------------------------------------------------------------------
class HisInvoiceDetailSync(models.Model):
    """Chi tiết từng dòng dịch vụ trong hóa đơn HIS."""

    his_ref_detail_id = models.CharField(max_length=100, unique=True, db_index=True, verbose_name='RefDetailID HIS')

    invoice_sync = models.ForeignKey(
        HisInvoiceSync,
        on_delete=models.CASCADE,
        related_name='details',
        verbose_name='Hóa đơn HIS',
        to_field='his_invoice_ref_id',
    )
    inventory_item_id = models.CharField(max_length=200, blank=True, verbose_name='InventoryItemID')
    inventory_item_code = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='Mã vật tư/DV')
    description = models.TextField(blank=True, verbose_name='Diễn giải')
    unit_name = models.CharField(max_length=50, blank=True, verbose_name='ĐVT')

    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=1, verbose_name='Số lượng')
    unit_price = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Đơn giá')
    amount = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Thành tiền')
    discount_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name='% CK')
    discount_amount = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Số tiền CK')
    vat_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name='% VAT')
    vat_amount = models.DecimalField(max_digits=16, decimal_places=4, default=0, verbose_name='Số tiền VAT')

    sort_order = models.IntegerField(default=0, verbose_name='Thứ tự')
    is_promotion = models.BooleanField(default=False, verbose_name='Khuyến mãi')
    inventory_item_type = models.IntegerField(default=0, verbose_name='Loại vật tư/DV')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_invoice_detail_sync'
        verbose_name = 'Chi tiết hóa đơn HIS'
        verbose_name_plural = 'Chi tiết hóa đơn HIS'
        indexes = [
            models.Index(fields=['invoice_sync']),
            models.Index(fields=['inventory_item_code']),
        ]

    def __str__(self):
        return f"{self.invoice_sync_id} - {self.description[:50]}"


# ---------------------------------------------------------------------------
# dbo.CauHinhDoiTuong — Cấu hình nghiệp vụ theo đối tượng bệnh nhân
# ---------------------------------------------------------------------------
class HisPatientTypeConfigSync(models.Model):
    """Cấu hình nghiệp vụ áp dụng cho từng đối tượng bệnh nhân."""

    his_config_id = models.BigIntegerField(unique=True, db_index=True, verbose_name='ID cấu hình HIS')

    patient_type_sync = models.ForeignKey(
        HisPatientTypeSync,
        on_delete=models.CASCADE,
        related_name='configs',
        verbose_name='Đối tượng BN HIS',
        to_field='his_patient_type_code',
    )
    patient_type_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Mã đối tượng BN')

    business_rule_code = models.CharField(max_length=100, blank=True, verbose_name='Mã nghiệp vụ')
    rule_value = models.CharField(max_length=200, blank=True, verbose_name='Giá trị xử lý')

    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'his_integration_patient_type_config_sync'
        verbose_name = 'Cấu hình đối tượng BN HIS'
        verbose_name_plural = 'Cấu hình đối tượng BN HIS'
        indexes = [
            models.Index(fields=['patient_type_code', 'business_rule_code']),
        ]

    def __str__(self):
        return f"{self.patient_type_code} — {self.business_rule_code}: {self.rule_value}"


# ---------------------------------------------------------------------------
# HisSyncJob (giữ nguyên, chỉ mở rộng ENTITY_CHOICES)
# ---------------------------------------------------------------------------
class HisSyncJob(models.Model):
    ENTITY_CHOICES = [
        ('patient', 'Bệnh nhân'),
        ('patient_type', 'Đối tượng BN'),
        ('patient_type_config', 'Cấu hình đối tượng BN'),
        ('corporate_package', 'Gói khám đoàn'),
        ('package_service', 'Dịch vụ theo gói đoàn'),
        ('service_catalog', 'Danh mục dịch vụ'),
        ('exam_record', 'Hồ sơ khám'),
        ('exam_service_item', 'Chi tiết dịch vụ KB'),
        ('diagnostic_imaging', 'Chẩn đoán hình ảnh'),
        ('functional_test', 'Thăm dò chức năng'),
        ('appointment', 'Lịch hẹn'),
        ('invoice', 'Hóa đơn'),
        ('invoice_detail', 'Chi tiết hóa đơn'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Chờ xử lý'),
        ('RUNNING', 'Đang chạy'),
        ('SUCCESS', 'Thành công'),
        ('FAILED', 'Thất bại'),
    ]
    
    entity_type = models.CharField(max_length=50, choices=ENTITY_CHOICES, verbose_name='Loại dữ liệu')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='Trạng thái')
    
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Bắt đầu')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Hoàn thành')
    
    total_records = models.IntegerField(default=0, verbose_name='Tổng số')
    synced_records = models.IntegerField(default=0, verbose_name='Đã đồng bộ')
    failed_records = models.IntegerField(default=0, verbose_name='Lỗi')
    
    error_log = models.JSONField(default=dict, blank=True, verbose_name='Log lỗi')
    
    triggered_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Người kích hoạt'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'his_integration_sync_job'
        verbose_name = 'Job đồng bộ HIS'
        verbose_name_plural = 'Job đồng bộ HIS'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_entity_type_display()} - {self.get_status_display()}"


_HIS_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_mau" / "manifest.json"
_HIS_SAMPLE_DIR = _HIS_MANIFEST_PATH.parent
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(?::\d{2})?$")


class HisLocalPgModel(models.Model):
    """Base unmanaged model for raw HIS tables imported into local PostgreSQL."""

    class Meta:
        abstract = True
        managed = False


@lru_cache(maxsize=1)
def _load_his_manifest() -> dict:
    if not _HIS_MANIFEST_PATH.exists():
        return {}
    return json.loads(_HIS_MANIFEST_PATH.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def _load_his_table_meta() -> dict[str, dict]:
    manifest = _load_his_manifest()
    return {
        item["table"].split(".", 1)[1]: item
        for item in manifest.get("tables_exported", [])
        if item.get("table", "").startswith("dbo.")
    }


@lru_cache(maxsize=1)
def _load_his_sample_rows() -> dict[str, list[dict]]:
    samples: dict[str, list[dict]] = {}
    for file_path in _HIS_SAMPLE_DIR.glob("dbo.*.json"):
        table_name = file_path.stem.split(".", 1)[1]
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            samples[table_name] = []
            continue

        if isinstance(raw, list):
            rows = [row for row in raw if isinstance(row, dict)]
        elif isinstance(raw, dict):
            rows = [value for value in raw.values() if isinstance(value, dict)]
            if not rows:
                rows = [raw]
        else:
            rows = []
        samples[table_name] = rows[:25]
    return samples


def _schema_table_name(table_name: str) -> str:
    return f'dbo"."{table_name}'


def _raw_model_name(table_name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", table_name)
    return f"HisDbo{cleaned}"


def _string_field_for_samples(values: list[str]) -> models.Field:
    if values and all(_ISO_DATETIME_RE.match(value) for value in values):
        return models.DateTimeField(null=True, blank=True)
    if values and all(_ISO_DATE_RE.match(value) for value in values):
        return models.DateField(null=True, blank=True)
    if values and all(_TIME_RE.match(value) for value in values):
        return models.TimeField(null=True, blank=True)
    max_len = max((len(value) for value in values), default=0)
    if 0 < max_len <= 255:
        return models.CharField(max_length=max(32, max_len), blank=True)
    return models.TextField(blank=True)


def _infer_raw_field(
    *,
    column_name: str,
    table_name: str,
    sample_rows: list[dict],
    primary_key_column: str,
):
    if column_name == primary_key_column:
        values = [row.get(column_name) for row in sample_rows if row.get(column_name) is not None]
        if values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            return models.BigIntegerField(primary_key=True)
        return models.CharField(max_length=255, primary_key=True)

    values = [row.get(column_name) for row in sample_rows if row.get(column_name) is not None]
    if values and all(isinstance(value, bool) for value in values):
        return models.BooleanField(null=True, blank=True)
    if values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return models.BigIntegerField(null=True, blank=True)
    if values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        return models.FloatField(null=True, blank=True)
    if values and all(isinstance(value, (dict, list)) for value in values):
        return models.JSONField(null=True, blank=True)
    if values and all(isinstance(value, str) for value in values):
        return _string_field_for_samples(values)

    if column_name.lower().startswith("b"):
        return models.BooleanField(null=True, blank=True)
    if "ngay" in column_name.lower() or column_name.lower() == "sysdate":
        return models.DateTimeField(null=True, blank=True)
    return models.TextField(blank=True)


def _assign_raw_db_column(field: models.Field, column_name: str) -> models.Field:
    if getattr(field, "db_column", None) in (None, ""):
        field.db_column = column_name
    return field


RAW_TABLE_PRIMARY_KEYS = {
    "DanhSachDichVuDinhNghiaTruocKhamTheoDoan": "MaDon",
    "DanhSachDichVuDinhNghiaTruocKhamTheoGoi": "MaDon",
    "DANHSACHPHANHE": "IDPhanhe",
    "DMBenhChuyenKhoaNT": "IDBenhChuyenKhoa",
    "DMBenhNhan": "MaBenhNhan",
    "DMDanToc": "MaDanToc",
    "DMDichVu": "MaDichVu",
    "DMDichVuChiTiet": "MaChiTieu",
    "DMDichVuKhamTheoGoi": "MaDichVu",
    "DMDoiTuongBaoHiem": "MaDoiTuongBaoHiem",
    "DMDoiTuongBenhNhan": "MaDoiTuongBenhNhan",
    "DMGioiTinh": "MaGioiTinh",
    "DMGoiDichVu": "MaGoiDichVu",
    "DMGoiDichVuChiTiet": "ID",
    "DMGoiKhamTheoDoan": "MaGoiKhamTheoDoan",
    "DMGoiVatTu": "MaGoiVatTu",
    "DMGoiVatTuChiTiet": "ID",
    "DMKhoa": "MaKhoa",
    "DMLoaiDichVu": "MaLoaiDichVu",
    "DMLyDoHuy_TangGiam": "MaLyDo",
    "DMNgheNghiep": "MaNgheNghiep",
    "DMNguoiDung": "MaNguoiDung",
    "DMNhomBaoHiem": "MaNhomBaoHiem",
    "DMNhomNguoiDung": "MaNhomNguoiDung",
    "DMPhanLoaiTheLuc": "ID",
    "DMPhongKham": "MaPhong",
    "DMQuanHuyen": "MaQuanHuyen",
    "DMQuocGia": "MaQuocGia",
    "DMTinhThanh": "MaTinhThanh",
    "DMTriSoBenhChuyenKhoaNT": "ID",
    "DMVoucher": "MaVoucher",
    "HoSoKhamBenhNgoaiTru": "MaHoSo",
    "HoSoKhamBenhNgoaiTru_Xoa": "MaHoSo",
    "LoaiGoiDichVuNT": "MaLoaiGoi",
    "PHANQUYENSUDUNG": "ID",
    "PhieuChanDoanHinhAnh": "MaChanDoanHinhAnh",
    "PhieuChanDoanHinhAnhChiTiet": "IDChanDoanHinhAnh",
    "PhieuKhamBenh": "MaKhamBenh",
    "PhieuKhamBenhChiTiet": "ID",
    "PhieuPhauThuatThuThuatTaiCho": "MaPhauThuatThuThuat",
    "PhieuPhauThuatThuThuatTaiChoChiTiet": "ID",
    "PhieuThamDoChucNang": "MaThamDoChucNang",
    "PhieuThamDoChucNangChiTiet": "ID",
    "PhieuXetNghiem": "MaXetNghiem",
    "PhieuXetNghiemChiTiet": "ID",
    "ThietLapVoucherTheoDichVu": "ID",
    "ThietLapVoucherTheoGoi": "ID",
    "ThuPhiDichVu": "MaThuPhi",
    "ThuPhiDichVuKhamTheoDoan": "MaThuPhi",
    "ThuPhiHuy": "MaThuPhiHuy",
}


RAW_TABLE_RELATION_OVERRIDES = {
    ("DMBenhNhan", "MaDanToc"): lambda: models.ForeignKey(
        "his_integration.HisDboDMDanToc",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="benh_nhan_set",
        db_column="MaDanToc",
        to_field="MaDanToc",
        db_constraint=False,
    ),
    ("DMBenhNhan", "MaGioiTinh"): lambda: models.ForeignKey(
        "his_integration.HisDboDMGioiTinh",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="benh_nhan_set",
        db_column="MaGioiTinh",
        to_field="MaGioiTinh",
        db_constraint=False,
    ),
    ("DMBenhNhan", "MaNgheNghiep"): lambda: models.ForeignKey(
        "his_integration.HisDboDMNgheNghiep",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="benh_nhan_set",
        db_column="MaNgheNghiep",
        to_field="MaNgheNghiep",
        db_constraint=False,
    ),
    ("HoSoKhamBenhNgoaiTru", "MaBenhNhan"): lambda: models.ForeignKey(
        "his_integration.HisDboDMBenhNhan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ho_so_ngoai_tru_set",
        db_column="MaBenhNhan",
        to_field="MaBenhNhan",
        db_constraint=False,
    ),
    ("HoSoKhamBenhNgoaiTru", "MaDoiTuongBenhNhan"): lambda: models.ForeignKey(
        "his_integration.HisDboDMDoiTuongBenhNhan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ho_so_ngoai_tru_set",
        db_column="MaDoiTuongBenhNhan",
        to_field="MaDoiTuongBenhNhan",
        db_constraint=False,
    ),
    ("HoSoKhamBenhNgoaiTru_Xoa", "MaGoiKhamTheoDoan"): lambda: models.ForeignKey(
        "his_integration.HisDboDMGoiKhamTheoDoan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ho_so_ngoai_tru_xoa_set",
        db_column="MaGoiKhamTheoDoan",
        to_field="MaGoiKhamTheoDoan",
        db_constraint=False,
    ),
    ("DMDichVuChiTiet", "MaDichVu"): lambda: models.ForeignKey(
        "his_integration.HisDboDMDichVu",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chi_tieu_set",
        db_column="MaDichVu",
        to_field="MaDichVu",
        db_constraint=False,
    ),
    ("ThuPhiDichVu", "MaChiTieu"): lambda: models.ForeignKey(
        "his_integration.HisDboDMDichVuChiTiet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="thu_phi_dich_vu_set",
        db_column="MaChiTieu",
        to_field="MaChiTieu",
        db_constraint=False,
    ),
}


def _build_raw_his_model(table_name: str, meta: dict):
    sample_rows = _load_his_sample_rows().get(table_name, [])
    columns = list(meta.get("columns", []))
    if not columns:
        return None

    primary_key_column = RAW_TABLE_PRIMARY_KEYS.get(table_name, columns[0])
    if primary_key_column not in columns:
        primary_key_column = columns[0]
    attrs = {
        "__module__": __name__,
        "__doc__": f"Raw unmanaged HIS table for dbo.{table_name}.",
    }
    for column_name in columns:
        override = RAW_TABLE_RELATION_OVERRIDES.get((table_name, column_name))
        field = override() if override else _infer_raw_field(
            column_name=column_name,
            table_name=table_name,
            sample_rows=sample_rows,
            primary_key_column=primary_key_column,
        )
        attrs[column_name] = _assign_raw_db_column(field, column_name)

    meta_class = type(
        "Meta",
        (),
        {
            "managed": False,
            "db_table": _schema_table_name(table_name),
            "app_label": "his_integration",
            "verbose_name": f"HIS dbo.{table_name}",
            "verbose_name_plural": f"HIS dbo.{table_name}",
        },
    )
    attrs["Meta"] = meta_class

    model_class = type(_raw_model_name(table_name), (HisLocalPgModel,), attrs)
    return model_class


def _resolve_goi_kham_theo_doan_parent(self):
    raw_code = (getattr(self, "MaGoiKhamTheoDoan", "") or "").strip()
    if not raw_code:
        return None

    package_model = globals().get("HisDboDMGoiKhamTheoDoan")
    if package_model is None:
        return None

    candidate = raw_code
    while candidate:
        package = package_model.objects.filter(MaGoiKhamTheoDoan=candidate).first()
        if package:
            return package
        if "." not in candidate:
            return None
        candidate = candidate.rsplit(".", 1)[0]
    return None


for _table_name, _table_meta in _load_his_table_meta().items():
    _model_name = _raw_model_name(_table_name)
    if _model_name not in globals():
        _model_class = _build_raw_his_model(_table_name, _table_meta)
        if _model_class is not None:
            globals()[_model_name] = _model_class

if "HisDboDanhSachDichVuDinhNghiaTruocKhamTheoGoi" in globals():
    HisDboDanhSachDichVuDinhNghiaTruocKhamTheoGoi.resolve_parent_package = _resolve_goi_kham_theo_doan_parent
    HisDboDanhSachDichVuDinhNghiaTruocKhamTheoGoi.parent_package = property(_resolve_goi_kham_theo_doan_parent)
