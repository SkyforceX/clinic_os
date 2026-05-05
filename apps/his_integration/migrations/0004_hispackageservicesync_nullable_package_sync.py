from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('his_integration', '0003_add_service_catalog_ft_appointment_invoice'),
    ]

    operations = [
        migrations.AddField(
            model_name='hispackageservicesync',
            name='his_package_code',
            field=models.CharField(blank=True, db_index=True, default='', max_length=50, verbose_name='Mã gói HIS'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='hispackageservicesync',
            name='package_sync',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='package_services',
                to='his_integration.hiscorporatepackagesync',
                to_field='his_package_code',
                verbose_name='Gói khám đoàn HIS',
            ),
        ),
    ]
