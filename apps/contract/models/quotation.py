from django.db import models
from django.conf import settings


class QuotationDraft(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_quotations",
    )
    contact_name = models.CharField(max_length=255, blank=True)
    company_name = models.CharField(max_length=255)
    company_address = models.CharField(max_length=500, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    # "Giá ưu đãi áp dụng cho số lượng khám dự kiến từ: ___ người"
    pax_from = models.PositiveIntegerField(null=True, blank=True, verbose_name="Ưu đãi từ (người)")

    # Số lượng từng nhóm (tuỳ chọn, để tính tổng tiền)
    male_count = models.PositiveIntegerField(default=0, verbose_name="Số lượng Nam")
    female_single_count = models.PositiveIntegerField(default=0, verbose_name="Số lượng Nữ độc thân")
    female_family_count = models.PositiveIntegerField(default=0, verbose_name="Số lượng Nữ gia đình")

    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    # Giảm giá toàn cục theo cột (thanh công cụ)
    discount_male_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Giảm % Nam")
    discount_fs_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Giảm % Nữ ĐT")
    discount_ff_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Giảm % Nữ GĐ")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_quotationdraft"
        ordering = ["-created_at"]
        verbose_name = "Báo giá"
        verbose_name_plural = "Danh sách báo giá"

    def __str__(self):
        return f"{self.company_name} ({self.created_at.strftime('%d/%m/%Y')})"

    @property
    def total_male(self):
        return sum(
            (int(line.price_male or 0))
            for line in self.lines.all()
            if line.checked_male
        )

    @property
    def total_female_single(self):
        return sum(
            (int(line.price_female_single or 0))
            for line in self.lines.all()
            if line.checked_female_single
        )

    @property
    def total_female_family(self):
        return sum(
            (int(line.price_female_family or 0))
            for line in self.lines.all()
            if line.checked_female_family
        )

    @property
    def grand_total(self):
        return (
            self.total_male * self.male_count
            + self.total_female_single * self.female_single_count
            + self.total_female_family * self.female_family_count
        )


class QuotationLine(models.Model):
    quotation = models.ForeignKey(
        QuotationDraft,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group_name = models.CharField(max_length=255, blank=True, null=True)
    subgroup_name = models.CharField(max_length=255, blank=True, null=True)

    # Giá ưu đãi theo từng nhóm đối tượng
    price_male = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_single = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_family = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    # Giá niêm yết (để hiển thị trên tài liệu)
    list_price = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    # Dịch vụ áp dụng cho nhóm nào
    checked_male = models.BooleanField(default=False)
    checked_female_single = models.BooleanField(default=False)
    checked_female_family = models.BooleanField(default=False)

    # Giá ưu đãi (sau khi áp giảm % toàn cục, trước khi áp giảm % từng dòng)
    udai_price_male   = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    udai_price_fs     = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    udai_price_ff     = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    # % giảm thêm riêng cho từng dòng (mỗi giới tính)
    discount_male_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_fs_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_ff_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Loại: standard | free | gift
    price_type = models.CharField(max_length=20, default="standard")
    note = models.CharField(max_length=100, blank=True, null=True)

    display_order = models.PositiveIntegerField(default=0)
    catalog_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "contract_quotationline"
        ordering = ["display_order"]

    def __str__(self):
        return self.item_name

    @property
    def display_price_male(self):
        if not self.checked_male:
            return None
        if self.price_type in ("free", "gift"):
            return self.note or "Miễn phí"
        return self.price_male

    @property
    def display_price_female_single(self):
        if not self.checked_female_single:
            return None
        if self.price_type in ("free", "gift"):
            return self.note or "Miễn phí"
        return self.price_female_single

    @property
    def display_price_female_family(self):
        if not self.checked_female_family:
            return None
        if self.price_type in ("free", "gift"):
            return self.note or "Miễn phí"
        return self.price_female_family
