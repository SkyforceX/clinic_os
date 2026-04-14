from django.db import models


class CorporateContractProfile(models.Model):
    contract = models.OneToOneField(
        "contract.Contract",
        on_delete=models.CASCADE,
        related_name="corporate_profile",
    )

    quotation = models.OneToOneField(
        "contract.QuotationDraft",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corporate_contract_profile",
    )

    quote_number = models.CharField(max_length=100, blank=True, null=True)
    quote_date = models.DateField(blank=True, null=True)

    contract_date = models.DateField(blank=True, null=True, verbose_name="Ngày lập hợp đồng")

    company_name_snapshot = models.CharField(max_length=255)
    company_address_snapshot = models.TextField(blank=True, null=True)
    company_tax_code_snapshot = models.CharField(max_length=100, blank=True, null=True)
    company_phone_snapshot = models.CharField(max_length=50, blank=True, null=True)

    contact_person_snapshot = models.CharField(max_length=255, blank=True, null=True)
    representative_title_snapshot = models.CharField(max_length=255, blank=True, null=True)

    male_count = models.PositiveIntegerField(default=0)
    female_single_count = models.PositiveIntegerField(default=0)
    female_family_count = models.PositiveIntegerField(default=0)

    signer_a_name = models.CharField(max_length=255, blank=True, null=True)
    signer_a_title = models.CharField(max_length=255, blank=True, null=True)
    signer_b_name = models.CharField(max_length=255, blank=True, null=True)
    signer_b_title = models.CharField(max_length=255, blank=True, null=True)

    quotation_note = models.TextField(blank=True, null=True)
    contract_note = models.TextField(blank=True, null=True)

    subtotal_male = models.BigIntegerField(default=0)
    subtotal_female_single = models.BigIntegerField(default=0)
    subtotal_female_family = models.BigIntegerField(default=0)
    grand_total = models.BigIntegerField(default=0)

    # Snapshot package + nội dung từ báo giá để hợp đồng độc lập hoàn toàn khi render/in
    package_snapshot_json = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Snapshot gói khám từ báo giá",
    )
    quotation_extra_content_snapshot = models.TextField(
        blank=True,
        null=True,
        verbose_name="Nội dung bổ sung snapshot từ báo giá",
    )

    # Giữ lại field cũ để tránh ảnh hưởng dữ liệu cũ
    blood_collection_time_from = models.TimeField(blank=True, null=True, verbose_name="Giờ bắt đầu lấy mẫu")
    blood_collection_time_to = models.TimeField(blank=True, null=True, verbose_name="Giờ kết thúc lấy mẫu")

    # Field mới: lưu đầy đủ ngày + giờ
    blood_collection_from_at = models.DateTimeField(blank=True, null=True, verbose_name="Ngày giờ bắt đầu lấy mẫu")
    blood_collection_to_at = models.DateTimeField(blank=True, null=True, verbose_name="Ngày giờ kết thúc lấy mẫu")

    blood_collection_location = models.CharField(max_length=500, blank=True, null=True, verbose_name="Địa điểm lấy mẫu")

    deposit_pct = models.DecimalField(max_digits=5, decimal_places=2, default=30, verbose_name="Tỷ lệ đặt cọc (%)")
    deposit_amount = models.BigIntegerField(default=0, verbose_name="Số tiền đặt cọc")
    deposit_amount_words = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Số tiền đặt cọc bằng chữ",
    )
    deposit_deadline = models.DateField(blank=True, null=True, verbose_name="Hạn đặt cọc trước ngày")

    settlement_days = models.PositiveIntegerField(default=10, verbose_name="Quyết toán trong vòng (ngày)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contracts_corporate_profile"
        ordering = ["-id"]
        verbose_name = "Corporate Contract Profile"
        verbose_name_plural = "Corporate Contract Profiles"

    def __str__(self):
        return f"{self.contract.contract_number} - corporate profile"