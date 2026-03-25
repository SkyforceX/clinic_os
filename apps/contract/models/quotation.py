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
    contact_name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    company_address = models.CharField(max_length=255, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class QuotationLine(models.Model):
    quotation = models.ForeignKey(
        QuotationDraft,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group_name = models.CharField(max_length=255, blank=True, null=True)

    price = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_male = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_single = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    price_female_family = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)

    checked_male = models.BooleanField(default=False)
    checked_female_single = models.BooleanField(default=False)
    checked_female_family = models.BooleanField(default=False)

    display_order = models.PositiveIntegerField(default=0)