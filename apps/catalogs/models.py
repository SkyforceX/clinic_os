from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class GroupCheckup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    group_en = models.CharField(max_length=255, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = "catalogs_group_checkup"
        ordering = ["display_order", "name", "id"]
        verbose_name = "Nhóm khám"
        verbose_name_plural = "Nhóm khám"

    def __str__(self):
        return self.name


class CheckupCategory(models.Model):
    PRICE_TYPE_STANDARD = "standard"
    PRICE_TYPE_FREE = "free"
    PRICE_TYPE_GIFT = "gift"

    PRICE_TYPE_CHOICES = [
        (PRICE_TYPE_STANDARD, "Tiêu chuẩn"),
        (PRICE_TYPE_FREE, "Miễn phí"),
        (PRICE_TYPE_GIFT, "Tặng"),
    ]

    group_checkup = models.ForeignKey(
        GroupCheckup,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    subgroup_name = models.CharField(max_length=255, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)

    item_code = models.CharField(max_length=50, blank=True, null=True, unique=True)
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # field cũ giữ lại để tương thích dữ liệu cũ / code cũ
    price = models.CharField(max_length=50, blank=True, null=True)

    list_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    price_type = models.CharField(
        max_length=20,
        choices=PRICE_TYPE_CHOICES,
        default=PRICE_TYPE_STANDARD,
    )

    price_male = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    price_female_single = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    price_female_family = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )

    for_male = models.BooleanField(default=True)
    for_female_single = models.BooleanField(default=True)
    for_female_family = models.BooleanField(default=True)

    note = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_checkup_categories",
        blank=True,
        null=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_checkup_categories",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = "catalogs_checkup_category"
        ordering = ["group_checkup__display_order", "group_checkup__name", "display_order", "id"]
        verbose_name = "Danh mục khám"
        verbose_name_plural = "Danh mục khám"

    def __str__(self):
        return self.item_name

    def save(self, *args, **kwargs):
        if self.item_name:
            self.item_name = self.item_name.strip()

        if self.subgroup_name:
            self.subgroup_name = self.subgroup_name.strip()

        if self.note:
            self.note = self.note.strip()

        if self.item_code:
            self.item_code = self.item_code.strip()

        if self.price in (None, ""):
            self.price = str(int(self.list_price or 0))

        super().save(*args, **kwargs)


class CheckupPackageTemplate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="checkup_package_templates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_checkup_package_templates",
        blank=True,
        null=True,
    )

    categories = models.ManyToManyField(
        CheckupCategory,
        through="CheckupPackageTemplateItem",
        related_name="package_templates",
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = "catalogs_checkup_package_template"
        ordering = ["-created_at", "-id"]
        verbose_name = "Gói khám mẫu"
        verbose_name_plural = "Gói khám mẫu"
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "name"],
                name="uq_catalogs_package_name_per_user",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def total_list_price(self):
        total = Decimal("0")
        for item in self.items.select_related("category").all():
            total += item.category.list_price or Decimal("0")
        return total


class CheckupPackageTemplateItem(models.Model):
    package = models.ForeignKey(
        CheckupPackageTemplate,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.ForeignKey(
        CheckupCategory,
        on_delete=models.CASCADE,
        related_name="package_items",
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalogs_checkup_package_template_item"
        ordering = ["display_order", "id"]
        verbose_name = "Dòng gói khám mẫu"
        verbose_name_plural = "Dòng gói khám mẫu"
        constraints = [
            models.UniqueConstraint(
                fields=["package", "category"],
                name="uq_catalogs_package_category",
            )
        ]

    def __str__(self):
        return f"{self.package_id} - {self.category_id}"