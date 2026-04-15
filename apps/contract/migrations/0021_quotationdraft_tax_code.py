from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contract", "0020_quotationdraft_contact_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotationdraft",
            name="tax_code",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
