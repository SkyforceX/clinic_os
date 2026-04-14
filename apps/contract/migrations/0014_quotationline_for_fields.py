from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0013_quotationdraft_commission_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotationline",
            name="for_male",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="quotationline",
            name="for_female_single",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="quotationline",
            name="for_female_family",
            field=models.BooleanField(default=True),
        ),
    ]
