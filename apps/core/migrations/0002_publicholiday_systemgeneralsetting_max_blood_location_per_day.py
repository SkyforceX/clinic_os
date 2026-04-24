from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemgeneralsetting",
            name="max_blood_location_per_day",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Nhập 0 để không giới hạn.",
                verbose_name="Số địa điểm lấy máu tối đa trong 1 ngày",
            ),
        ),
        migrations.CreateModel(
            name="PublicHoliday",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True, verbose_name="Ngày nghỉ")),
                ("name", models.CharField(blank=True, max_length=100, verbose_name="Tên ngày nghỉ")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Ngày nghỉ lễ",
                "verbose_name_plural": "Ngày nghỉ lễ",
                "db_table": "core_public_holiday",
                "ordering": ["date"],
            },
        ),
    ]
