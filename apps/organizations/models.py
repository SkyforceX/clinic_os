import uuid

from django.conf import settings
from django.db import models


class Company(models.Model):
    """
    Normalized organization model.

    Phase 2.1:
    - Chuyển ownership từ bảng legacy `clinic_company` sang bảng mới `organizations_company`
    - Giữ nguyên PK để data migration an toàn và các FK có thể chuyển dần ở phase sau
    """

    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=False, blank=True)
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True, null=True)
    tax_code = models.CharField(max_length=50, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_companies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations_company"
        ordering = ["-id"]
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name