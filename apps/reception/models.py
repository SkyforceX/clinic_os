"""
apps/reception/models.py
=========================
Model ghi nhận check-in / check-out khách hàng doanh nghiệp.

Thiết kế:
- FK soft đến Patient và ContractScheduleConfig (nullable để tránh cascade xóa mất dữ liệu)
- Snapshot các trường quan trọng để không bị mất dữ liệu nếu công ty / bệnh nhân bị xóa
- Mỗi lần check-in = 1 bản ghi; cùng 1 ngày có thể check-out rồi check-in lại
"""

from django.conf import settings
from django.db import models


class CheckInStatus(models.TextChoices):
    CHECKED_IN  = "CHECKED_IN",  "Đã check-in"
    CHECKED_OUT = "CHECKED_OUT", "Đã check-out"
    DEFERRED    = "DEFERRED",    "Quay lại sau"


class CheckInRecord(models.Model):
    """
    Bản ghi tiếp nhận khách hàng tại quầy lễ tân.

    Snapshot: lưu lại thông tin tại thời điểm check-in để không bị mất
    nếu bản ghi gốc (Patient, Company, Contract) bị thay đổi hoặc xóa.
    """

    # ── Liên kết mềm (FK nullable) ─────────────────────────────────────────
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_records",
        verbose_name="Bệnh nhân",
    )
    his_patient_sync = models.ForeignKey(
        "his_integration.HisPatientSync",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_records",
        verbose_name="Bệnh nhân HIS",
    )
    schedule_config = models.ForeignKey(
        "scheduling.ContractScheduleConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_records",
        verbose_name="Cấu hình lịch khám",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_records",
        verbose_name="Công ty",
    )

    # ── Snapshot thông tin bệnh nhân tại thời điểm check-in ───────────────
    snapshot_ma_bn       = models.CharField(max_length=20, verbose_name="Mã bệnh nhân")
    snapshot_ho_ten      = models.CharField(max_length=100, verbose_name="Họ và tên")
    snapshot_gioi_tinh   = models.CharField(max_length=10, blank=True, verbose_name="Giới tính")
    snapshot_ngay_sinh   = models.DateField(null=True, blank=True, verbose_name="Ngày sinh")
    snapshot_company_name = models.CharField(max_length=200, blank=True, verbose_name="Tên công ty")
    snapshot_exam_start  = models.DateField(null=True, blank=True, verbose_name="Ngày bắt đầu khám")
    snapshot_exam_end    = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc khám")

    # ── Trạng thái và thời gian ────────────────────────────────────────────
    exam_date = models.DateField(
        db_index=True,
        verbose_name="Ngày khám thực tế",
        help_text="Ngày khách hàng thực sự đến khám (không phải khung lịch).",
    )
    status = models.CharField(
        max_length=16,
        choices=CheckInStatus.choices,
        default=CheckInStatus.CHECKED_IN,
        db_index=True,
        verbose_name="Trạng thái",
    )
    checked_in_at  = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian check-in")
    checked_out_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian check-out")
    deferred_at    = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian hoãn")

    # ── Ghi chú và người thực hiện ────────────────────────────────────────
    note     = models.TextField(blank=True, verbose_name="Ghi chú")
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_operations",
        verbose_name="Thư ký thực hiện",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reception_checkin_record"
        verbose_name = "Bản ghi check-in"
        verbose_name_plural = "Bản ghi check-in / check-out"
        ordering = ["-exam_date", "-checked_in_at"]
        indexes = [
            models.Index(fields=["exam_date", "status"], name="reception_ci_date_status_idx"),
            models.Index(fields=["snapshot_ma_bn", "exam_date"], name="reception_ci_mabn_date_idx"),
            models.Index(fields=["his_patient_sync", "status"], name="reception_ci_his_status_idx"),
        ]

    def __str__(self):
        return f"{self.snapshot_ma_bn} – {self.snapshot_ho_ten} ({self.exam_date})"

    @property
    def gioi_tinh_display(self):
        mapping = {"Nam": "Nam", "Nữ": "Nữ", "MALE": "Nam", "FEMALE": "Nữ", "M": "Nam", "F": "Nữ"}
        return mapping.get(self.snapshot_gioi_tinh, self.snapshot_gioi_tinh)
