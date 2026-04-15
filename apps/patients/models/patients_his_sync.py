from django.db import models
from django.utils import timezone


class HisPatientSync(models.Model):
    """
    Mirror dữ liệu HIS từ bảng dbo.DMBenhNhan.
    Không thay thế model bệnh nhân nghiệp vụ hiện có.
    Dùng để lưu bản sao đồng bộ + đối soát + incremental sync.
    """

    # --- khóa HIS ---
    his_patient_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name="Mã bệnh nhân HIS",
    )  # MaBenhNhan

    his_patient_auto_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Mã bệnh nhân tự sinh HIS",
    )  # MaBenhNhanTuSinh

    stt = models.BigIntegerField(null=True, blank=True)  # STT
    his_sysdate = models.DateTimeField(null=True, blank=True)  # sysdate

    # --- thông tin cơ bản ---
    full_name = models.CharField(max_length=200, null=True, blank=True)  # TenBenhNhan
    birth_date_text = models.CharField(max_length=20, null=True, blank=True)  # NgayThang
    birth_year = models.IntegerField(null=True, blank=True)  # NamSinh
    gender_code = models.CharField(max_length=50, null=True, blank=True)  # MaGioiTinh

    ethnicity_code = models.CharField(max_length=50, null=True, blank=True)  # MaDanToc
    occupation_code = models.CharField(max_length=50, null=True, blank=True)  # MaNgheNghiep
    country_code = models.CharField(max_length=50, null=True, blank=True)  # MaQuocGia

    province_code = models.CharField(max_length=50, null=True, blank=True)  # MaTinhThanh
    district_code = models.CharField(max_length=50, null=True, blank=True)  # MaQuanHuyen
    ward_code = models.CharField(max_length=50, null=True, blank=True)  # MaXa

    hamlet_address = models.CharField(max_length=400, null=True, blank=True)  # ThonPho
    work_place = models.CharField(max_length=400, null=True, blank=True)  # NoiLamViec

    phone = models.CharField(max_length=510, null=True, blank=True)  # SoDienThoai
    phone_enabled = models.CharField(max_length=600, null=True, blank=True)  # SoDienThoaiEnabled
    email = models.CharField(max_length=510, null=True, blank=True)  # Email

    emergency_contact_name = models.CharField(
        max_length=510, null=True, blank=True
    )  # NguoiCanBaoTin
    emergency_contact_phone = models.CharField(
        max_length=50, null=True, blank=True
    )  # NguoiCanBaoTin_SDT

    # --- sinh trắc / ảnh / chữ ký ---
    fingerprint_1 = models.TextField(null=True, blank=True)  # VanTay1
    fingerprint_2 = models.TextField(null=True, blank=True)  # VanTay2
    fingerprint_3 = models.TextField(null=True, blank=True)  # VanTay3

    patient_image = models.BinaryField(null=True, blank=True)  # HinhAnhBenhNhan
    patient_signature = models.BinaryField(null=True, blank=True)  # ChuKyBenhNhan
    relative_signature = models.BinaryField(null=True, blank=True)  # ChuKyNguoiNha

    # --- cờ trạng thái ---
    outpatient_treatment_flag = models.BooleanField(
        null=True, blank=True
    )  # bDieuTriNgoaiTru
    completed_treatment_flag = models.BooleanField(
        null=True, blank=True
    )  # bDaDieuTriXong
    receive_online_result = models.BooleanField(
        null=True, blank=True
    )  # NhanKetQuaOnline
    vip_flag = models.BooleanField(default=False)  # bVip
    kiosk_checkin_flag = models.BooleanField(null=True, blank=True)  # bTiepNhanKiot

    # --- công tác / đơn vị ---
    rank_code = models.CharField(max_length=50, null=True, blank=True)  # MaCapBacCongTac
    unit_code = models.CharField(max_length=50, null=True, blank=True)  # MaDonViCongTac
    employee_code = models.CharField(max_length=50, null=True, blank=True)  # MaNhanVien
    client_source_code = models.CharField(max_length=50, null=True, blank=True)  # MaNguonKhach
    vip_card_code = models.CharField(max_length=50, null=True, blank=True)  # MaTheVip

    # --- địa chỉ / giấy tờ ---
    address = models.CharField(max_length=2048, null=True, blank=True)  # DiaChiBenhNhan
    full_address_label = models.CharField(
        max_length=2048, null=True, blank=True
    )  # TenXaPhuongQuanHuyenTinhThanh

    national_id = models.CharField(max_length=510, null=True, blank=True)  # SoCMT
    national_id_issue_date = models.DateTimeField(null=True, blank=True)  # NgayCap / NgayCapCMT
    national_id_issue_place = models.CharField(max_length=510, null=True, blank=True)  # NoiCap
    national_id_issue_place_code = models.CharField(
        max_length=50, null=True, blank=True
    )  # MaNoiCapCMT

    passport_number = models.CharField(max_length=50, null=True, blank=True)  # SoHoChieu
    passport_issue_place = models.CharField(
        max_length=1000, null=True, blank=True
    )  # NoiCapHoChieu
    passport_issue_date = models.DateTimeField(null=True, blank=True)  # NgayCapHoChieu

    hometown = models.CharField(max_length=510, null=True, blank=True)  # QueQuan
    household_address = models.CharField(max_length=400, null=True, blank=True)  # HoKhauTT

    # --- nghĩa vụ / gia đình / độ tuổi ---
    enlist_date = models.DateTimeField(null=True, blank=True)  # NgayNhapNgu
    discharge_date = models.DateTimeField(null=True, blank=True)  # NgayXuatNgu
    reserve_date = models.DateTimeField(null=True, blank=True)  # NgayTaiNgu
    family_status_code = models.CharField(max_length=50, null=True, blank=True)  # IDTrangThaiGiaDinh

    age_in_months = models.IntegerField(null=True, blank=True)  # ThangTuoi
    age_in_weeks = models.CharField(max_length=50, null=True, blank=True)  # TuanTuoi
    age_in_hours = models.CharField(max_length=50, null=True, blank=True)  # GioTuoi

    chronic_disease_flag = models.IntegerField(null=True, blank=True)  # BenhManTinh
    long_term_treatment_flag = models.IntegerField(null=True, blank=True)  # DieuTriDaiNgay

    # --- địa chỉ cũ ---
    old_province_code = models.CharField(max_length=50, null=True, blank=True)  # MaTinhThanhCu
    old_district_code = models.CharField(max_length=50, null=True, blank=True)  # MaQuanHuyenCu
    old_ward_code = models.CharField(max_length=50, null=True, blank=True)  # MaXaCu
    old_address = models.CharField(max_length=510, null=True, blank=True)  # DiaChiCu

    # --- khác ---
    server_source = models.IntegerField(null=True, blank=True)  # TuMayChu
    note = models.TextField(null=True, blank=True)  # GhiChu
    warning_note = models.CharField(max_length=1000, null=True, blank=True)  # LuuY
    password_raw = models.CharField(max_length=1000, null=True, blank=True)  # MatKhau

    # --- audit sync ---
    raw_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patients_his_patient_sync"
        verbose_name = "HIS Patient Sync"
        verbose_name_plural = "HIS Patient Sync"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.his_patient_code} - {self.full_name or ''}".strip()


class HisSyncState(models.Model):
    """
    Lưu mốc đồng bộ incremental.
    Khuyên dùng MaBenhNhanTuSinh làm cursor vì là bigint identity.
    """

    source = models.CharField(max_length=50, unique=True, default="his_dmbenhnhan")
    last_auto_id = models.BigIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patients_his_sync_state"
        verbose_name = "HIS Sync State"
        verbose_name_plural = "HIS Sync State"

    def __str__(self) -> str:
        return f"{self.source}: {self.last_auto_id}"