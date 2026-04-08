from django.db import models


class ImplementationPlan(models.Model):
    contract = models.OneToOneField(
        "contract.Contract",
        on_delete=models.CASCADE,
        related_name="implementation_plan",
    )
    rows_json = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contract_implementation_plan"
        ordering = ["-id"]
        verbose_name = "Kế hoạch triển khai"
        verbose_name_plural = "Kế hoạch triển khai"

    def __str__(self):
        return f"Kế hoạch triển khai - {self.contract.contract_number or self.contract_id}"