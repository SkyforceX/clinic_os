from django.db import models


class CorporateContractProfile(models.Model):
    contract = models.OneToOneField(
        "booking.HealthContract",
        on_delete=models.CASCADE,
        related_name="corporate_profile",
    )

    quote_number = models.CharField(max_length=100, blank=True, null=True)
    quote_date = models.DateField(blank=True, null=True)

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contracts_corporate_profile"
        ordering = ["-id"]
        verbose_name = "Corporate Contract Profile"
        verbose_name_plural = "Corporate Contract Profiles"

    def __str__(self):
        return f"{self.contract.contract_number} - corporate profile"