from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reception", "0003_checkinrecord_his_patient_sync"),
    ]

    operations = [
        migrations.AlterField(
            model_name="checkinrecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("CHECKED_IN",  "Đã check-in"),
                    ("CHECKED_OUT", "Đã check-out"),
                    ("DEFERRED",    "Quay lại sau"),
                    ("CANCELLED",   "Đã hủy khám"),
                ],
                db_index=True,
                default="CHECKED_IN",
                max_length=16,
                verbose_name="Trạng thái",
            ),
        ),
    ]
