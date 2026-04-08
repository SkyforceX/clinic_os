from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0015_implementationplanlog"),
    ]

    operations = [
        # Thêm extra_content vào QuotationDraft
        migrations.AddField(
            model_name="quotationdraft",
            name="extra_content",
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name="Nội dung bổ sung (HTML)",
            ),
        ),
        # Tạo model QuotationPackage
        migrations.CreateModel(
            name="QuotationPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "quotation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="packages",
                        to="contract.quotationdraft",
                    ),
                ),
                ("name", models.CharField(max_length=255, verbose_name="Tên gói khám")),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("columns_json", models.JSONField(default=list, verbose_name="Cột đối tượng")),
            ],
            options={
                "verbose_name": "Gói khám trong báo giá",
                "verbose_name_plural": "Gói khám trong báo giá",
                "db_table": "contract_quotationpackage",
                "ordering": ["display_order", "id"],
            },
        ),
    ]
