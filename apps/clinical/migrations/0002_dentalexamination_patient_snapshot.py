from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dentalexamination",
            name="patient_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
