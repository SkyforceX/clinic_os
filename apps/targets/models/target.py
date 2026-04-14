"""
targets/models/target.py
=========================
Quản lý KPI & Quota bán hàng theo cá nhân / team, theo tháng / quý / năm.
"""
from django.conf import settings
from django.db import models


class PeriodType(models.TextChoices):
    MONTHLY   = "MONTHLY",   "Tháng"
    QUARTERLY = "QUARTERLY", "Quý"
    YEARLY    = "YEARLY",    "Năm"


class SalesTarget(models.Model):
    """
    KPI / Quota cho từng sale theo từng kỳ.

    user=NULL → target team (tổng công ty).
    period_number: 1-12 (tháng), 1-4 (quý), 1 (năm).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sales_targets",
        verbose_name="Sale phụ trách",
        help_text="Để trống = target tổng team",
    )

    period_type   = models.CharField(max_length=12, choices=PeriodType.choices, db_index=True)
    year          = models.PositiveIntegerField(db_index=True)
    period_number = models.PositiveSmallIntegerField(
        help_text="1-12 (tháng) / 1-4 (quý) / 1 (năm)"
    )

    # ── Chỉ tiêu doanh thu ────────────────────────────────────────────────────
    revenue_target       = models.BigIntegerField(default=0, verbose_name="Doanh thu mục tiêu (VNĐ)")
    contract_count_target = models.PositiveIntegerField(default=0, verbose_name="Số HĐ mục tiêu")
    quotation_count_target = models.PositiveIntegerField(default=0, verbose_name="Số báo giá mục tiêu")
    pax_target           = models.PositiveIntegerField(default=0, verbose_name="Số người khám mục tiêu")

    # ── Chỉ tiêu tài chính nâng cao ───────────────────────────────────────────
    new_client_target    = models.PositiveIntegerField(default=0, verbose_name="Số KH mới mục tiêu")
    renewal_target       = models.PositiveIntegerField(default=0, verbose_name="Số HĐ gia hạn mục tiêu")
    avg_deal_size_target = models.BigIntegerField(default=0, verbose_name="Giá trị HĐ TB mục tiêu")

    # ── Metadata ──────────────────────────────────────────────────────────────
    notes      = models.TextField(blank=True, verbose_name="Ghi chú")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sales_targets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "targets_sales_target"
        ordering = ["-year", "period_type", "period_number"]
        verbose_name = "KPI Sale"
        verbose_name_plural = "KPI Sale"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "period_type", "year", "period_number"],
                name="uq_targets_user_period",
            )
        ]

    def __str__(self):
        name = self.user.get_full_name() if self.user else "Team"
        return f"{name} – {self.get_period_type_display()} {self.period_number}/{self.year}"

    @property
    def period_label(self) -> str:
        if self.period_type == PeriodType.MONTHLY:
            return f"T{self.period_number}/{self.year}"
        if self.period_type == PeriodType.QUARTERLY:
            return f"Q{self.period_number}/{self.year}"
        return str(self.year)

    @property
    def is_team_target(self) -> bool:
        return self.user_id is None


class TargetNote(models.Model):
    """Nhật ký / comment gắn vào một kỳ target (activity log)."""

    target = models.ForeignKey(
        SalesTarget,
        on_delete=models.CASCADE,
        related_name="target_notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="target_notes_authored",
    )
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "targets_target_note"
        ordering = ["-created_at"]
        verbose_name = "Ghi chú KPI"
