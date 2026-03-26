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
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name=_("Bệnh nhân"),
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
        ]
        indexes = [
            models.Index(fields=["status", "booked_at"]),
            models.Index(fields=["schedule_slot", "status"]),
            models.Index(fields=["patient", "status"]),
        ]

    def __str__(self):
        patient_name = getattr(self.patient, "ho_ten", None) or str(self.patient)
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