from django.db import models


class GroupCheckup(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "catalogs_group_checkup"
        ordering = ["name"]
        verbose_name = "Nhóm khám"
        verbose_name_plural = "Nhóm khám"

    def __str__(self):
        return self.name


class CheckupCategory(models.Model):
    group_checkup = models.ForeignKey(
        GroupCheckup,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = "catalogs_checkup_category"
        ordering = ["group_checkup__name", "id"]
        verbose_name = "Danh mục khám"
        verbose_name_plural = "Danh mục khám"

    def __str__(self):
        return self.item_name