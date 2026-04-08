from django.conf import settings
from django.db import models


class VoucherType(models.TextChoices):
    DEPOSIT    = "DEPOSIT",    "Đặt cọc"
    SETTLEMENT = "SETTLEMENT", "Quyết toán"
    OTHER      = "OTHER",      "Khác"


class VoucherStatus(models.TextChoices):
    DRAFT     = "DRAFT",     "Nháp"
    SUBMITTED = "SUBMITTED", "Chờ duyệt"
    APPROVED  = "APPROVED",  "Đã duyệt"
    PAID      = "PAID",      "Đã thanh toán"
    CANCELLED = "CANCELLED", "Hủy"


class PaymentVoucher(models.Model):
    """
    Phiếu thanh toán gắn với hợp đồng doanh nghiệp.
    Một hợp đồng có thể có nhiều phiếu (đặt cọc, quyết toán, điều chỉnh...).

    Luồng trạng thái: DRAFT → SUBMITTED → APPROVED → PAID
                                         └──────────────→ CANCELLED
    """

    contract = models.ForeignKey(
        "contract.Contract",
        on_delete=models.CASCADE,
        related_name="payment_vouchers",
        verbose_name="Hợp đồng",
    )
    voucher_type = models.CharField(
        max_length=20,
        choices=VoucherType.choices,
        default=VoucherType.DEPOSIT,
        verbose_name="Loại phiếu",
    )
    status = models.CharField(
        max_length=20,
        choices=VoucherStatus.choices,
        default=VoucherStatus.DRAFT,
        db_index=True,
        verbose_name="Trạng thái",
    )

    amount       = models.BigIntegerField(verbose_name="Số tiền (VND)")
    amount_words = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Số tiền bằng chữ",
    )
    due_date = models.DateField(null=True, blank=True, verbose_name="Hạn thanh toán")
    paid_at  = models.DateField(null=True, blank=True, verbose_name="Ngày đã thanh toán")
    note     = models.TextField(blank=True, verbose_name="Ghi chú")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payment_vouchers",
        verbose_name="Người tạo",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_payment_voucher"
        ordering = ["-created_at"]
        verbose_name = "Phiếu thanh toán"
        verbose_name_plural = "Phiếu thanh toán"

    def __str__(self):
        contract_num = self.contract.contract_number or f"#{self.contract_id}"
        return f"{self.get_voucher_type_display()} — {contract_num} — {self.amount:,.0f} VND"

    @property
    def is_editable(self) -> bool:
        return self.status == VoucherStatus.DRAFT

    @property
    def is_approved(self) -> bool:
        return self.status in (VoucherStatus.APPROVED, VoucherStatus.PAID)
