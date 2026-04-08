from decimal import Decimal

from django.conf import settings
from django.db import models


class ContractStatus(models.TextChoices):
    DRAFT = "DRAFT", "Nháp"
    SUBMITTED = "SUBMITTED", "Chờ duyệt"
    APPROVED = "APPROVED", "Đã duyệt"
    ACTIVE = "ACTIVE", "Đang hiệu lực"
    FINISHED = "FINISHED", "Hoàn tất"
    TERMINATED = "TERMINATED", "Chấm dứt"
    CANCELLED = "CANCELLED", "Hủy"


ACTIVE_STATUSES = (
    ContractStatus.APPROVED,
    ContractStatus.ACTIVE,
)

CLOSED_STATUSES = (
    ContractStatus.FINISHED,
    ContractStatus.TERMINATED,
    ContractStatus.CANCELLED,
)


class ContractNumberSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_value = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_number_sequence"
        verbose_name = "Bộ đếm số hợp đồng"
        verbose_name_plural = "Bộ đếm số hợp đồng"
        ordering = ["-year"]

    def __str__(self):
        return f"{self.year}: {self.last_value}"


class Contract(models.Model):
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_number = models.CharField(max_length=50, unique=True, null=True, blank=True)

    contact_person = models.CharField(max_length=255, blank=True)
    representative_title = models.CharField(max_length=255, blank=True)

    employee_count = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reception_from_date = models.DateField(null=True, blank=True)

    contract_value_text = models.TextField(blank=True, null=True)
    deposit_payment_text = models.TextField(blank=True, null=True)
    settlement_time_text = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        db_index=True,
    )

    is_locked = models.BooleanField(default=False, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_contracts",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_contracts",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_contracts",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract_number"],
                name="uq_contract_company_number",
            )
        ]

    def __str__(self):
        return f"{self.company.name} - {self.contract_number or self.pk}"

    @property
    def year(self) -> int | None:
        if self.start_date:
            return self.start_date.year
        if self.created_at:
            return self.created_at.year
        return None

    @property
    def is_approved(self) -> bool:
        return self.status in (
            ContractStatus.APPROVED,
            ContractStatus.ACTIVE,
            ContractStatus.FINISHED,
        )

    @property
    def is_finished(self) -> bool:
        return self.status == ContractStatus.FINISHED

    @property
    def is_terminated(self) -> bool:
        return self.status == ContractStatus.TERMINATED

    @property
    def is_editable(self) -> bool:
        return not self.is_locked and not self.is_approved

    def distribute_slots(self):
        from apps.scheduling.services.allocate_slots import allocate_contract_slots

        return allocate_contract_slots(contract=self)


class ContractServiceLine(models.Model):
    PRICE_TYPE_STANDARD = "standard"
    PRICE_TYPE_FREE = "free"
    PRICE_TYPE_GIFT = "gift"

    PRICE_TYPE_CHOICES = (
        (PRICE_TYPE_STANDARD, "Tiêu chuẩn"),
        (PRICE_TYPE_FREE, "Miễn phí"),
        (PRICE_TYPE_GIFT, "Tặng"),
    )

    contract = models.ForeignKey(
        "contract.Contract",
        on_delete=models.CASCADE,
        related_name="service_lines",
    )

    source_quotation_line_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )

    catalog_service = models.ForeignKey(
        "catalogs.CheckupCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_lines",
    )

    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    group_name = models.CharField(max_length=255, blank=True, null=True)
    subgroup_name = models.CharField(max_length=255, blank=True, null=True)
    group_name_en = models.CharField(max_length=255, blank=True, null=True)

    for_male = models.BooleanField(default=False)
    for_female_single = models.BooleanField(default=False)
    for_female_family = models.BooleanField(default=False)

    price_male = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True)
    price_female_single = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True)
    price_female_family = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True)

    price_type = models.CharField(
        max_length=20,
        choices=PRICE_TYPE_CHOICES,
        default=PRICE_TYPE_STANDARD,
    )

    note = models.CharField(max_length=255, blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chi tiết dịch vụ hợp đồng"
        verbose_name_plural = "Chi tiết dịch vụ hợp đồng"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.contract.contract_number} - {self.item_name}"

    def get_price(self, gender: str) -> int:
        field = f"price_{gender}"
        value = getattr(self, field, None)
        if value in (None, ""):
            return 0
        if isinstance(value, Decimal):
            return int(value)
        try:
            return int(value)
        except Exception:
            return 0