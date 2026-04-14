from django.conf import settings
from django.db import models


class ProposalType(models.TextChoices):
    PRICE_CHANGE = "PRICE_CHANGE", "Thay đổi giá"
    SCOPE_CHANGE = "SCOPE_CHANGE", "Thay đổi phạm vi dịch vụ"
    EXTENSION    = "EXTENSION",    "Gia hạn hợp đồng"
    DISCOUNT     = "DISCOUNT",     "Điều chỉnh chiết khấu"
    OTHER        = "OTHER",        "Khác"


class ProposalStatus(models.TextChoices):
    DRAFT     = "DRAFT",     "Nháp"
    SUBMITTED = "SUBMITTED", "Chờ duyệt"
    APPROVED  = "APPROVED",  "Đã duyệt"
    EXECUTED  = "EXECUTED",  "Đã thực hiện"
    REJECTED  = "REJECTED",  "Từ chối"
    CANCELLED = "CANCELLED", "Hủy"


class ProposalForm(models.Model):
    """
    Phiếu đề xuất thay đổi nội bộ: giá, phạm vi, gia hạn...

    Luồng trạng thái: DRAFT → SUBMITTED → APPROVED → EXECUTED
                                          └──────────────────→ REJECTED

    Có thể không gắn hợp đồng (contract=None) khi đề xuất độc lập.
    """

    contract = models.ForeignKey(
        "contract.Contract",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="proposals",
        verbose_name="Hợp đồng liên quan",
    )
    proposal_type = models.CharField(
        max_length=30,
        choices=ProposalType.choices,
        verbose_name="Loại đề xuất",
    )
    status = models.CharField(
        max_length=20,
        choices=ProposalStatus.choices,
        default=ProposalStatus.DRAFT,
        db_index=True,
        verbose_name="Trạng thái",
    )

    title   = models.CharField(max_length=255, verbose_name="Tiêu đề")
    content = models.TextField(verbose_name="Nội dung đề xuất")
    amount  = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Giá trị tài chính liên quan (VND)",
    )
    note = models.TextField(blank=True, verbose_name="Ghi chú")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_proposals",
        verbose_name="Người tạo",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_proposal_form"
        ordering = ["-created_at"]
        verbose_name = "Phiếu đề xuất"
        verbose_name_plural = "Phiếu đề xuất"

    def __str__(self):
        return f"[{self.get_proposal_type_display()}] {self.title}"

    @property
    def is_editable(self) -> bool:
        return self.status == ProposalStatus.DRAFT

    @property
    def is_approved(self) -> bool:
        return self.status in (ProposalStatus.APPROVED, ProposalStatus.EXECUTED)
