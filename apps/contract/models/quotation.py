from django.db import models
from django.conf import settings


class QuotationStatus(models.TextChoices):
    DRAFT     = "DRAFT",     "Nháp"
    SUBMITTED = "SUBMITTED", "Chờ duyệt"
    APPROVED  = "APPROVED",  "Đã duyệt"
    REJECTED  = "REJECTED",  "Từ chối"


STANDARD_COL_KEYS = {"male", "female_single", "female_family"}

DEFAULT_PACKAGE_COLUMNS = [
    {"key": "male",          "label": "NAM",          "count": 0, "discount_pct": 0},
    {"key": "female_single", "label": "NỮ ĐỘC THÂN",  "count": 0, "discount_pct": 0},
    {"key": "female_family", "label": "NỮ GIA ĐÌNH",  "count": 0, "discount_pct": 0},
]


class QuotationDraft(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_quotations",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="quotations",
    )
    contact_name    = models.CharField(max_length=255, blank=True)
    contact_phone   = models.CharField(max_length=50, blank=True)
    tax_code        = models.CharField(max_length=100, blank=True)
    company_name    = models.CharField(max_length=255)
    company_address = models.CharField(max_length=500, blank=True)
    valid_until     = models.DateField(null=True, blank=True)

    pax_from = models.PositiveIntegerField(null=True, blank=True, verbose_name="Ưu đãi từ (người)")

    # Kept for backward compat with old single-package quotations
    male_count          = models.PositiveIntegerField(default=0, verbose_name="Số lượng Nam")
    female_single_count = models.PositiveIntegerField(default=0, verbose_name="Số lượng Nữ độc thân")
    female_family_count = models.PositiveIntegerField(default=0, verbose_name="Số lượng Nữ gia đình")

    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")

    # Kept for backward compat
    discount_male_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Giảm % Nam")
    discount_fs_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Giảm % Nữ ĐT")
    discount_ff_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Giảm % Nữ GĐ")

    commission_sale_pct    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="% Hoa hồng Sale")
    commission_sale_amount = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name="Hoa hồng Sale (VNĐ)")
    commission_co_pct      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="% Hoa hồng Công ty")
    commission_co_amount   = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name="Hoa hồng Công ty (VNĐ)")

    # Rich-text nội dung bổ sung (Quill HTML) — hiển thị sau toàn bộ bảng giá
    extra_content = models.TextField(blank=True, null=True, verbose_name="Nội dung bổ sung (HTML)")

    status = models.CharField(
        max_length=20,
        choices=QuotationStatus.choices,
        default=QuotationStatus.DRAFT,
        db_index=True,
        verbose_name="Trạng thái",
    )

    is_locked = models.BooleanField(default=False, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="locked_quotations",
    )

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
    def is_editable(self) -> bool:
        return self.status == QuotationStatus.DRAFT and not self.is_locked

    @property
    def is_approved(self) -> bool:
        return self.status == QuotationStatus.APPROVED

    @property
    def total_male(self):
        return sum(
            int(line.price_male or 0)
            for line in self.lines.all()
            if line.checked_male
        )

    @property
    def total_female_single(self):
        return sum(
            int(line.price_female_single or 0)
            for line in self.lines.all()
            if line.checked_female_single
        )

    @property
    def total_female_family(self):
        return sum(
            int(line.price_female_family or 0)
            for line in self.lines.all()
            if line.checked_female_family
        )

    @property
    def grand_total(self):
        packages = list(self.packages.prefetch_related("lines").all())
        if packages:
            total = 0
            for pkg in packages:
                # Cache lines một lần — tránh N+1 query khi lặp qua nhiều columns
                pkg_lines = list(pkg.lines.all())
                for col in (pkg.columns_json or []):
                    key   = col.get("key", "")
                    count = int(col.get("count") or 0)
                    if count <= 0:
                        continue
                    if key == "male":
                        per_person = sum(int(l.price_male or 0) for l in pkg_lines if l.checked_male)
                    elif key == "female_single":
                        per_person = sum(int(l.price_female_single or 0) for l in pkg_lines if l.checked_female_single)
                    elif key == "female_family":
                        per_person = sum(int(l.price_female_family or 0) for l in pkg_lines if l.checked_female_family)
                    else:
                        per_person = sum(
                            int((l.extra_prices_json or {}).get(key) or 0)
                            for l in pkg_lines
                        )
                    total += per_person * count
            return total
        # Legacy single-package
        return (
            self.total_male * self.male_count
            + self.total_female_single * self.female_single_count
            + self.total_female_family * self.female_family_count
        )

    @property
    def corporate_contract(self):
        profile = getattr(self, "corporate_contract_profile", None)
        return getattr(profile, "contract", None) if profile else None

    @property
    def has_corporate_contract(self):
        return self.corporate_contract is not None

    @property
    def pending_approval_request(self):
        return self.approval_requests.filter(status="PENDING").first()


class QuotationPackage(models.Model):
    """Một gói khám trong báo giá — mỗi gói là một bảng giá độc lập."""

    quotation    = models.ForeignKey(QuotationDraft, on_delete=models.CASCADE, related_name="packages")
    name         = models.CharField(max_length=255, verbose_name="Tên gói khám")
    display_order = models.PositiveIntegerField(default=0)

    # Danh sách cột đối tượng:
    # [{"key": "male", "label": "NAM", "count": 50, "discount_pct": 5.0}, ...]
    # Standard keys: "male", "female_single", "female_family"
    # Custom keys:   "cx_0", "cx_1", ...
    columns_json = models.JSONField(default=list, verbose_name="Cột đối tượng")

    class Meta:
        db_table = "contract_quotationpackage"
        ordering = ["display_order", "id"]
        verbose_name = "Gói khám trong báo giá"
        verbose_name_plural = "Gói khám trong báo giá"

    def __str__(self):
        return f"{self.quotation} – {self.name}"


class QuotationLine(models.Model):
    quotation   = models.ForeignKey(QuotationDraft, on_delete=models.CASCADE, related_name="lines")
    # Nếu None → dòng thuộc báo giá cũ (1 gói duy nhất, không có QuotationPackage)
    package     = models.ForeignKey(
        QuotationPackage,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="lines",
    )

    item_name   = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group_name    = models.CharField(max_length=255, blank=True, null=True)
    subgroup_name = models.CharField(max_length=255, blank=True, null=True)

    price_male          = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_single = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_family = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    list_price = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    checked_male          = models.BooleanField(default=False)
    checked_female_single = models.BooleanField(default=False)
    checked_female_family = models.BooleanField(default=False)

    udai_price_male = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    udai_price_fs   = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    udai_price_ff   = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    discount_male_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_fs_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_ff_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    price_type = models.CharField(max_length=20, default="standard")
    note       = models.CharField(max_length=100, blank=True, null=True)

    for_male          = models.BooleanField(default=True)
    for_female_single = models.BooleanField(default=True)
    for_female_family = models.BooleanField(default=True)

    # Giá cho các cột tùy chỉnh (custom columns trong package)
    # {"cx_0": 500000, "cx_0_udai": 520000, "cx_1": 300000, "cx_1_udai": 310000}
    extra_prices_json = models.JSONField(default=dict, verbose_name="Giá cột tùy chỉnh")

    display_order = models.PositiveIntegerField(default=0)
    catalog_id    = models.PositiveIntegerField(null=True, blank=True)

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
