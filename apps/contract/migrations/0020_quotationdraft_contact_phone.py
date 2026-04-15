from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0019_implementationplan_is_published"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotationdraft",
            name="contact_phone",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
