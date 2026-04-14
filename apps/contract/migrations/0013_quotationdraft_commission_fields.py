from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0012_alter_paymentvoucher_id_alter_proposalform_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotationdraft",
            name="commission_sale_pct",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
                verbose_name="% Hoa hồng Sale",
            ),
        ),
        migrations.AddField(
            model_name="quotationdraft",
            name="commission_sale_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                max_digits=15,
                null=True,
                verbose_name="Hoa hồng Sale (VNĐ)",
            ),
        ),
        migrations.AddField(
            model_name="quotationdraft",
            name="commission_co_pct",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
                verbose_name="% Hoa hồng Công ty",
            ),
        ),
        migrations.AddField(
            model_name="quotationdraft",
            name="commission_co_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                max_digits=15,
                null=True,
                verbose_name="Hoa hồng Công ty (VNĐ)",
            ),
        ),
    ]
