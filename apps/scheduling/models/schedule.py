from django.conf import settings
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
    quotation = models.ForeignKey(
        "contract.QuotationDraft",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="schedule_slots",
        verbose_name=_("Báo giá"),
    )
    date = models.DateField(verbose_name=_("Ngày khám"))
    shift = models.CharField(
        max_length=20,
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
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(slot_type=SlotType.CONTRACT)
                        & (models.Q(contract__isnull=False) | models.Q(quotation__isnull=False))
                    )
                    |
                    (
                        models.Q(slot_type=SlotType.INDIVIDUAL)
                        & models.Q(contract__isnull=True)
                        & models.Q(quotation__isnull=True)
                    )
                ),
                name="ck_schedule_slot_owner_valid",
            ),
            models.UniqueConstraint(
                fields=["date", "shift", "slot_type", "contract"],
                condition=models.Q(contract__isnull=False),
                name="uq_schedule_slot_date_shift_type_contract",
            ),
            models.UniqueConstraint(
                fields=["date", "shift", "slot_type", "quotation"],
                condition=models.Q(contract__isnull=True, quotation__isnull=False),
                name="uq_schedule_slot_date_shift_type_quotation",
            ),
        ]
        indexes = [
            models.Index(fields=["date", "shift"]),
            models.Index(fields=["slot_type", "status"]),
            models.Index(fields=["contract", "date"]),
            models.Index(fields=["quotation", "date"]),
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

        if self.slot_type == SlotType.CONTRACT and not (self.contract_id or self.quotation_id):
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {"contract": _("Slot loại hợp đồng bắt buộc phải có contract hoặc quotation.")}
            )

        if self.slot_type == SlotType.INDIVIDUAL and (self.contract_id or self.quotation_id):
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {"contract": _("Slot khách lẻ không được gắn contract hoặc quotation.")}
            )


class ContractScheduleConfig(models.Model):
    """
    Cấu hình lịch khám cho một báo giá / hợp đồng.
    """

    contract = models.OneToOneField(
        "contract.CorporateContractProfile",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="schedule_config",
        verbose_name=_("Hợp đồng"),
    )
    quotation = models.OneToOneField(
        "contract.QuotationDraft",
        on_delete=models.CASCADE,
        related_name="schedule_config",
        verbose_name=_("Báo giá"),
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="registered_contract_schedule_configs",
        verbose_name=_("Người đăng ký"),
    )
    exam_start_date = models.DateField(verbose_name=_("Ngày bắt đầu khám"))
    exam_end_date = models.DateField(verbose_name=_("Ngày kết thúc khám"))
    planned_employee_count = models.PositiveIntegerField(default=0, verbose_name=_("Số khách hàng đăng ký"))
    am_capacity_limit = models.PositiveIntegerField(default=0, verbose_name=_("Giới hạn slot sáng"))
    pm_capacity_limit = models.PositiveIntegerField(default=0, verbose_name=_("Giới hạn slot chiều"))
    created_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Ngày tạo"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Cập nhật lúc"))

    class Meta:
        db_table = "contract_schedule_config"
        ordering = ["-updated_at", "-id"]
        verbose_name = _("Cấu hình lịch khám hợp đồng")
        verbose_name_plural = _("Cấu hình lịch khám hợp đồng")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(planned_employee_count__gte=0),
                name="contract_schedule_cfg_employee_count_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(am_capacity_limit__gte=0),
                name="contract_schedule_cfg_am_limit_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(pm_capacity_limit__gte=0),
                name="contract_schedule_cfg_pm_limit_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(exam_end_date__gte=models.F("exam_start_date")),
                name="contract_schedule_cfg_end_date_gte_start_date",
            ),
        ]
        indexes = [
            models.Index(fields=["quotation"], name="contract_sc_quotation_idx"),
            models.Index(fields=["contract"], name="contract_sc_contract_idx"),
            models.Index(fields=["exam_start_date", "exam_end_date"], name="contract_sc_exam_range_idx"),
        ]

    def __str__(self):
        q_id = self.quotation_id or "—"
        return f"ScheduleConfig #{self.pk} (Quotation #{q_id})"


class ScheduleBloodCollectionRow(models.Model):
    """
    Hàng lịch lấy máu chi tiết gắn với ContractScheduleConfig.
    """

    schedule_config = models.ForeignKey(
        ContractScheduleConfig,
        on_delete=models.CASCADE,
        related_name="blood_collection_rows",
        verbose_name=_("Lịch đăng ký khám"),
    )
    collection_date = models.DateField(verbose_name=_("Ngày lấy máu"))
    location = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Địa điểm"))
    people_count = models.PositiveIntegerField(default=0, verbose_name=_("Số khách hàng"))
    staff_count = models.PositiveIntegerField(default=0, verbose_name=_("Số điều dưỡng"))
    created_at = models.DateTimeField(blank=True, null=True, verbose_name=_("Ngày tạo"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Cập nhật lúc"))

    class Meta:
        db_table = "schedule_blood_collection_row"
        ordering = ["collection_date", "id"]
        indexes = [
            models.Index(fields=["schedule_config", "collection_date"], name="sched_blood_cfg_date_idx"),
            models.Index(fields=["collection_date"], name="sched_blood_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(people_count__gte=0),
                name="sched_blood_people_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(staff_count__gte=0),
                name="sched_blood_staff_gte_0",
            ),
        ]

    def __str__(self):
        return f"{self.collection_date} – {self.location or '—'}"