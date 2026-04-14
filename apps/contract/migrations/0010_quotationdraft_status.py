# Generated for clinic_os — bước 1 hệ thống phê duyệt

from django.db import migrations, models


class Migration(migrations.Migration):
    """Thêm field status vào QuotationDraft."""

    dependencies = [
        ("contract", "0009_contractserviceline_discount_ff_pct_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotationdraft",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT",     "Nháp"),
                    ("SUBMITTED", "Chờ duyệt"),
                    ("APPROVED",  "Đã duyệt"),
                    ("REJECTED",  "Từ chối"),
                ],
                db_index=True,
                default="DRAFT",
                max_length=20,
                verbose_name="Trạng thái",
            ),
        ),
    ]
