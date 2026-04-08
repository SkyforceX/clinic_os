from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeShift(models.TextChoices):
    MORNING = "AM", _("Sáng")
    AFTERNOON = "PM", _("Chiều")


class SlotType(models.TextChoices):
    INDIVIDUAL = "INDIVIDUAL", _("Khách lẻ")
    CONTRACT = "CONTRACT", _("Khách đoàn / hợp đồng")


class SlotStatus(models.TextChoices):
    OPEN = "OPEN", _("Mở")
    CLOSED = "CLOSED", _("Đóng")
    CANCELLED = "CANCELLED", _("Hủy")


class ScheduleSlot(models.Model):
    """
    Slot lịch khám thuộc app scheduling.

    Vai trò:
    - Chỉ mô tả năng lực tiếp nhận / khung lịch có thể đăng ký
    - Có thể là slot cho khách lẻ hoặc slot dành riêng cho hợp đồng
    - Không chứa logic hồ sơ bệnh nhân hay bản ghi đặt khám cụ thể
    """

    contract = models.ForeignKey(
        "contract.Contract",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="schedule_slots",
        verbose_name=_("Hợp đồng"),
    )
    date = models.DateField(verbose_name=_("Ngày khám"))
    shift = models.CharField(
        max_length=2,
        choices=TimeShift.choices,
        verbose_name=_("Buổi"),
    )
    slot_type = models.CharField(
        max_length=20,
        choices=SlotType.choices,
        default=SlotType.INDIVIDUAL,
        db_index=True,
        verbose_name=_("Loại slot"),
    )
    capacity = models.PositiveIntegerField(default=0, verbose_name=_("Sức chứa"))
    booked_count = models.PositiveIntegerField(default=0, verbose_name=_("Đã đăng ký"))
    status = models.CharField(
        max_length=12,
        choices=SlotStatus.choices,
        default=SlotStatus.OPEN,
        db_index=True,
        verbose_name=_("Trạng thái"),
    )
    note = models.TextField(blank=True, verbose_name=_("Ghi chú"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Tạo lúc"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Cập nhật lúc"))

    class Meta:
        db_table = "scheduling_schedule_slot"
        ordering = ["date", "shift", "id"]
        verbose_name = _("Slot lịch khám")
        verbose_name_plural = _("Slot lịch khám")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity__gte=0),
                name="ck_schedule_slot_capacity_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(booked_count__gte=0),
                name="ck_schedule_slot_booked_count_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(booked_count__lte=models.F("capacity")),
                name="ck_schedule_slot_booked_not_exceed_capacity",
            ),
            models.UniqueConstraint(
                fields=["date", "shift", "slot_type", "contract"],
                name="uq_schedule_slot_date_shift_type_contract",
            ),
        ]
        indexes = [
            models.Index(fields=["date", "shift"]),
            models.Index(fields=["slot_type", "status"]),
            models.Index(fields=["contract", "date"]),
        ]

    def __str__(self):
        contract_part = f" - HĐ #{self.contract_id}" if self.contract_id else ""
        return f"{self.date} {self.get_shift_display()} - {self.get_slot_type_display()}{contract_part}"

    @property
    def remaining_capacity(self):
        return max(self.capacity - self.booked_count, 0)

    @property
    def is_open_for_booking(self):
        return self.status == SlotStatus.OPEN and self.remaining_capacity > 0

    def clean(self):
        super().clean()

        if self.slot_type == SlotType.CONTRACT and not self.contract_id:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {"contract": _("Slot loại hợp đồng bắt buộc phải có contract.")}
            )

        if self.slot_type == SlotType.INDIVIDUAL and self.contract_id:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {"contract": _("Slot khách lẻ không được gắn contract.")}
            )