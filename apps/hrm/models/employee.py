import uuid

from django.conf import settings
from django.db import models


class EmploymentType(models.TextChoices):
    FULLTIME   = "FULLTIME",   "Chính thức toàn thời gian"
    PARTTIME   = "PARTTIME",   "Bán thời gian"
    PROBATION  = "PROBATION",  "Thử việc"
    CONTRACT   = "CONTRACT",   "Hợp đồng có thời hạn"
    INTERNSHIP = "INTERNSHIP", "Thực tập"


class EmployeeStatus(models.TextChoices):
    PROBATION  = "PROBATION",  "Đang thử việc"
    ACTIVE     = "ACTIVE",     "Đang làm việc"
    RESIGNED   = "RESIGNED",   "Đã nghỉ việc"
    TERMINATED = "TERMINATED", "Bị chấm dứt"
    ON_LEAVE   = "ON_LEAVE",   "Đang nghỉ phép dài hạn"


class GenderChoice(models.TextChoices):
    MALE   = "MALE",   "Nam"
    FEMALE = "FEMALE", "Nữ"
    OTHER  = "OTHER",  "Khác"


class Employee(models.Model):
    """
    Hồ sơ nhân viên clinic_os – Phase 1.

    Liên kết 1-1 với Django User (null cho phép tạo hồ sơ trước khi cấp tài khoản).
    Mọi thay đổi trạng thái đi qua service layer (onboard / offboard / transfer).
    """

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # ── Tài khoản hệ thống ────────────────────────────────────────────────────
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profile",
        verbose_name="Tài khoản hệ thống",
    )

    # ── Mã nhân viên ─────────────────────────────────────────────────────────
    employee_code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Mã nhân viên",
        help_text="Tự sinh hoặc nhập theo quy tắc nội bộ. VD: NV-2024-001",
    )

    # ── Thông tin cá nhân ────────────────────────────────────────────────────
    full_name       = models.CharField(max_length=150, verbose_name="Họ và tên")
    gender          = models.CharField(max_length=10, choices=GenderChoice.choices, blank=True, verbose_name="Giới tính")
    date_of_birth   = models.DateField(null=True, blank=True, verbose_name="Ngày sinh")
    phone           = models.CharField(max_length=20, blank=True, verbose_name="Số điện thoại")
    email           = models.EmailField(blank=True, verbose_name="Email cá nhân")
    address         = models.TextField(blank=True, verbose_name="Địa chỉ thường trú")

    # ── Giấy tờ pháp lý ──────────────────────────────────────────────────────
    id_card_number      = models.CharField(max_length=20, blank=True, verbose_name="Số CCCD / CMND")
    id_card_issued_date = models.DateField(null=True, blank=True, verbose_name="Ngày cấp")
    id_card_issued_by   = models.CharField(max_length=200, blank=True, verbose_name="Nơi cấp")
    tax_code            = models.CharField(max_length=20, blank=True, verbose_name="Mã số thuế cá nhân")
    social_insurance_code = models.CharField(max_length=20, blank=True, verbose_name="Số BHXH")
    bank_account        = models.CharField(max_length=30, blank=True, verbose_name="Số tài khoản ngân hàng")
    bank_name           = models.CharField(max_length=100, blank=True, verbose_name="Ngân hàng")

    # ── Vị trí công việc ─────────────────────────────────────────────────────
    department = models.ForeignKey(
        "hrm.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="Phòng ban",
    )
    position = models.ForeignKey(
        "hrm.Position",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="Chức vụ",
    )
    direct_manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
        verbose_name="Quản lý trực tiếp",
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULLTIME,
        verbose_name="Loại hình công việc",
    )

    # ── Ngày tháng ───────────────────────────────────────────────────────────
    hire_date          = models.DateField(null=True, blank=True, verbose_name="Ngày vào làm")
    probation_end_date = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc thử việc")
    official_date      = models.DateField(null=True, blank=True, verbose_name="Ngày chính thức")
    resignation_date   = models.DateField(null=True, blank=True, verbose_name="Ngày nghỉ việc")

    # ── Trạng thái ───────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.PROBATION,
        db_index=True,
        verbose_name="Trạng thái",
    )

    # ── Liên hệ khẩn cấp ─────────────────────────────────────────────────────
    emergency_contact_name  = models.CharField(max_length=150, blank=True, verbose_name="Tên người liên hệ khẩn cấp")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, verbose_name="SĐT khẩn cấp")
    emergency_contact_rel   = models.CharField(max_length=50, blank=True, verbose_name="Quan hệ")

    # ── Ghi chú ──────────────────────────────────────────────────────────────
    note = models.TextField(blank=True, verbose_name="Ghi chú nội bộ")

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_employees",
        verbose_name="Người tạo hồ sơ",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hrm_employee"
        ordering = ["full_name"]
        verbose_name = "Nhân viên"
        verbose_name_plural = "Nhân viên"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["department"]),
        ]

    def __str__(self):
        return f"{self.employee_code} – {self.full_name}"

    @property
    def is_active(self) -> bool:
        return self.status in (EmployeeStatus.ACTIVE, EmployeeStatus.ON_LEAVE)

    @property
    def display_position(self) -> str:
        parts = []
        if self.position:
            parts.append(self.position.name)
        if self.department:
            parts.append(self.department.name)
        return " / ".join(parts) if parts else "—"
