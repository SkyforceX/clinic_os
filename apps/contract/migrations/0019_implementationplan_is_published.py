from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0018_corporatecontractprofile_package_snapshot_json_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="implementationplan",
            name="is_published",
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name="Đã công khai",
            ),
        ),
    ]
