from django.db import models


class ContractServiceLine(models.Model):
    contract = models.ForeignKey(
        "contract.Contract",
        on_delete=models.CASCADE,
        related_name="service_lines",
    )
    catalog_service = models.ForeignKey(
        "catalogs.CheckupService",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_lines",
    )

    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group_name = models.CharField(max_length=255, blank=True, null=True)

    for_male = models.BooleanField(default=False)
    for_female_single = models.BooleanField(default=False)
    for_female_family = models.BooleanField(default=False)

    price_male = models.CharField(max_length=50, blank=True, null=True)
    price_female_single = models.CharField(max_length=50, blank=True, null=True)
    price_female_family = models.CharField(max_length=50, blank=True, null=True)

    note = models.CharField(max_length=255, blank=True, null=True)

    display_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)