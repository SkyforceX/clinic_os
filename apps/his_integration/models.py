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


class HisSyncJob(models.Model):
    ENTITY_CHOICES = [
        ('patient', 'Bệnh nhân'),
        ('patient_type', 'Đối tượng BN'),
        ('corporate_package', 'Gói khám đoàn'),
        ('exam_record', 'Hồ sơ khám'),
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
