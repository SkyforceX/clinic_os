from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0016_quotationpackage"),
    ]

    operations = [
        # Thêm FK package vào QuotationLine (nullable để backward compat)
        migrations.AddField(
            model_name="quotationline",
            name="package",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lines",
                to="contract.quotationpackage",
            ),
        ),
        # Thêm extra_prices_json cho giá cột tùy chỉnh
        migrations.AddField(
            model_name="quotationline",
            name="extra_prices_json",
            field=models.JSONField(default=dict, verbose_name="Giá cột tùy chỉnh"),
        ),
    ]
