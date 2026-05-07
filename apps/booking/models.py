from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AppointmentStatus(models.TextChoices):
    PENDING = "PENDING", _("Chờ xác nhận")
    CONFIRMED = "CONFIRMED", _("Đã xác nhận")
    CHECKED_IN = "CHECKED_IN", _("Đã check-in")
    IN_PROGRESS = "IN_PROGRESS", _("Đang khám")
    COMPLETED = "COMPLETED", _("Hoàn thành")
    CANCELLED = "CANCELLED", _("Hủy")
    NO_SHOW = "NO_SHOW", _("Vắng")


class BookingSource(models.TextChoices):
    WEB_FORM = "WEB_FORM", _("Web form")
    HOTLINE = "HOTLINE", _("Hotline")
    STAFF = "STAFF", _("Nhân viên nhập")
    QR_OFFLINE = "QR_OFFLINE", _("QR offline")
    IMPORT = "IMPORT", _("Import")
    OTHER = "OTHER", _("Khác")


class Appointment(models.Model):
    """
    Lịch hẹn thực tế đã gắn với bệnh nhân.

    Vai trò:
    - Đại diện cho một đăng ký khám cụ thể
    - Gắn patient với một schedule slot
    - Không chứa định nghĩa slot / capacity
    """

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name=_("Bệnh nhân"),
    )
    his_patient_sync = models.ForeignKey(
        "his_integration.HisPatientSync",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name=_("Bệnh nhân HIS"),
    )
    schedule_slot = models.ForeignKey(
        "scheduling.ScheduleSlot",
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name=_("Slot lịch"),
    )
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_appointments",
        verbose_name=_("Nhân viên phụ trách"),
    )
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.CONFIRMED,
        db_index=True,
        verbose_name=_("Trạng thái"),
    )
    note = models.TextField(blank=True, verbose_name=_("Ghi chú"))

    booked_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Đặt lúc"))
    checked_in_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Check-in lúc"),
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Hủy lúc"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Hoàn thành lúc"),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Tạo lúc"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Cập nhật lúc"))

    class Meta:
        db_table = "booking_appointment"
        ordering = ["-booked_at", "-id"]
        verbose_name = _("Lịch hẹn")
        verbose_name_plural = _("Lịch hẹn")
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "schedule_slot"],
                name="uq_booking_appointment_patient_schedule_slot",
            ),
            models.UniqueConstraint(
                fields=["his_patient_sync", "schedule_slot"],
                name="uq_booking_appointment_his_patient_schedule_slot",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "booked_at"]),
            models.Index(fields=["schedule_slot", "status"]),
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["his_patient_sync", "status"]),
            models.Index(fields=["schedule_slot", "his_patient_sync"]),
        ]

    def __str__(self):
        patient_name = (
            getattr(self.his_patient_sync, "full_name", None)
            or getattr(self.patient, "ho_ten", None)
            or str(self.patient or self.his_patient_sync)
        )
        return f"{patient_name} - {self.schedule_slot}"


class IndividualBooking(models.Model):
    """
    Phiếu đăng ký khám cho khách lẻ chưa định danh thành Patient.

    Sau khi xác nhận và tạo Patient chính thức thì có thể link sang Appointment.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Chờ xác nhận")
        CONFIRMED = "CONFIRMED", _("Đã xác nhận")
        CHECKED_IN = "CHECKED_IN", _("Đã đến quầy")
        CONVERTED = "CONVERTED", _("Đã tạo bệnh nhân/lịch hẹn")
        CANCELLED = "CANCELLED", _("Hủy")
        NO_SHOW = "NO_SHOW", _("Vắng")

    schedule_slot = models.ForeignKey(
        "scheduling.ScheduleSlot",
        on_delete=models.PROTECT,
        related_name="individual_bookings",
        verbose_name=_("Slot lịch"),
    )

    full_name = models.CharField(max_length=120, verbose_name=_("Họ tên"))
    gender = models.CharField(max_length=10, blank=True, verbose_name=_("Giới tính"))
    dob = models.DateField(null=True, blank=True, verbose_name=_("Ngày sinh"))
    phone = models.CharField(max_length=20, db_index=True, verbose_name=_("Số điện thoại"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))
    address = models.TextField(blank=True, null=True, verbose_name=_("Địa chỉ"))
    id_number = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name=_("CCCD/CMND"),
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Lý do khám"),
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_("Trạng thái"),
    )
    note = models.TextField(blank=True, verbose_name=_("Ghi chú"))

    patient = models.ForeignKey(
        "patients.Patient",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="individual_bookings",
        verbose_name=_("Bệnh nhân đã chuyển đổi"),
    )
    appointment = models.OneToOneField(
        "booking.Appointment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="from_individual_booking",
        verbose_name=_("Lịch hẹn đã tạo"),
    )

    source = models.CharField(
        max_length=20,
        choices=BookingSource.choices,
        default=BookingSource.OTHER,
        blank=True,
        verbose_name=_("Nguồn tạo"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_individual_bookings",
        verbose_name=_("Người tạo"),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Tạo lúc"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Cập nhật lúc"))

    class Meta:
        db_table = "booking_individual_booking"
        ordering = ["-created_at", "-id"]
        verbose_name = _("Đăng ký khách lẻ")
        verbose_name_plural = _("Đăng ký khách lẻ")
        indexes = [
            models.Index(fields=["phone", "status"]),
            models.Index(fields=["schedule_slot", "status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule_slot", "phone"],
                condition=models.Q(status__in=["PENDING", "CONFIRMED", "CHECKED_IN"]),
                name="uq_active_individual_booking_phone_per_slot",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone}) @ {self.schedule_slot}"


class HisAppointmentPushLog(models.Model):
    """
    Ghi nhận từng lần push lịch hẹn lên HIS AppService.

    Tạo ngay khi dispatch Celery task (status=QUEUED),
    cập nhật khi task chạy xong (SUCCESS / FAILED / SKIPPED).
    """

    class PushStatus(models.TextChoices):
        QUEUED  = "QUEUED",  _("Đã xếp hàng")
        SUCCESS = "SUCCESS", _("Thành công")
        FAILED  = "FAILED",  _("Thất bại")
        SKIPPED = "SKIPPED", _("Bỏ qua")

    appointment = models.ForeignKey(
        "booking.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="his_push_logs",
        verbose_name=_("Lịch hẹn"),
    )
    status = models.CharField(
        max_length=10,
        choices=PushStatus.choices,
        default=PushStatus.QUEUED,
        db_index=True,
        verbose_name=_("Trạng thái"),
    )
    attempt = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Lần thử"),
    )
    endpoint = models.CharField(max_length=500, blank=True, verbose_name=_("Endpoint"))
    payload = models.JSONField(null=True, blank=True, verbose_name=_("Payload gửi đi"))
    http_status_code = models.IntegerField(null=True, blank=True, verbose_name=_("HTTP status"))
    response_data = models.JSONField(null=True, blank=True, verbose_name=_("Response JSON"))
    response_text = models.TextField(blank=True, verbose_name=_("Response text"))
    error = models.TextField(blank=True, verbose_name=_("Lỗi"))
    skipped_reason = models.TextField(blank=True, verbose_name=_("Lý do bỏ qua"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Tạo lúc"))
    pushed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Push xong lúc"))

    class Meta:
        db_table = "booking_his_push_log"
        ordering = ["-created_at"]
        verbose_name = _("HIS Push Log")
        verbose_name_plural = _("HIS Push Logs")
        indexes = [
            models.Index(fields=["status", "created_at"], name="bk_hislog_status_creat_idx"),
            models.Index(fields=["appointment", "created_at"], name="bk_hislog_appt_creat_idx"),
        ]

    def __str__(self):
        appt_id = self.appointment_id or "—"
        return f"PushLog #{self.pk} appt={appt_id} [{self.status}] @ {self.created_at:%d/%m/%Y %H:%M}"
