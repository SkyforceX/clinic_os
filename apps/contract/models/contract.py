from django.db import models
from django.conf import settings


class ContractStatus(models.TextChoices):
    DRAFT      = "DRAFT",      "Nháp"
    SUBMITTED  = "SUBMITTED",  "Chờ duyệt"
    APPROVED   = "APPROVED",   "Đã duyệt"
    ACTIVE     = "ACTIVE",     "Đang hiệu lực"
    FINISHED   = "FINISHED",   "Hoàn tất"
    TERMINATED = "TERMINATED", "Chấm dứt"
    CANCELLED  = "CANCELLED",  "Hủy"


# Các trạng thái coi là "còn hiệu lực" (dùng để lọc danh sách hợp đồng đang hoạt động)
ACTIVE_STATUSES = (
    ContractStatus.APPROVED,
    ContractStatus.ACTIVE,
)

# Các trạng thái coi là "đã kết thúc" (không hiển thị mặc định)
CLOSED_STATUSES = (
    ContractStatus.FINISHED,
    ContractStatus.TERMINATED,
    ContractStatus.CANCELLED,
)


class Contract(models.Model):
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_number = models.CharField(max_length=50, unique=True, null=True, blank=True)

    contact_person       = models.CharField(max_length=255, blank=True)
    representative_title = models.CharField(max_length=255, blank=True)

    employee_count     = models.PositiveIntegerField(null=True, blank=True)
    start_date         = models.DateField(null=True, blank=True)
    end_date           = models.DateField(null=True, blank=True)
    reception_from_date = models.DateField(null=True, blank=True)

    contract_value_text  = models.TextField(blank=True, null=True)
    deposit_payment_text = models.TextField(blank=True, null=True)
    settlement_time_text = models.TextField(blank=True, null=True)
    note                 = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        db_index=True,
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
    approved_at    = models.DateTimeField(null=True, blank=True)
    terminated_at  = models.DateField(null=True, blank=True)

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

    # ------------------------------------------------------------------
    # Backward-compat properties
    # Các code cũ (booking/views.py, scheduling selectors) kiểm tra
    # is_approved / is_finished / is_terminated trực tiếp trên object.
    # Giữ nguyên interface, đổi cách tính dựa trên field `status`.
    # ------------------------------------------------------------------

    @property
    def year(self) -> int | None:
        if self.start_date:
            return self.start_date.year
        if self.created_at:
            return self.created_at.year
        return None

    @property
    def is_approved(self) -> bool:
        """True nếu hợp đồng đã qua bước duyệt (approved, active, finished)."""
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

    # ------------------------------------------------------------------
    # Scheduling integration
    # ------------------------------------------------------------------

    def distribute_slots(self):
        """Phân bổ slot khám cho toàn bộ khung ngày của hợp đồng."""
        from apps.scheduling.services.allocate_slots import allocate_contract_slots
        return allocate_contract_slots(contract=self)
