import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("his_integration", "0001_initial"),
        ("reception", "0002_alter_checkinrecord_exam_date_alter_checkinrecord_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="checkinrecord",
            name="his_patient_sync",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="checkin_records",
                to="his_integration.hispatientsync",
                verbose_name="Bệnh nhân HIS",
            ),
        ),
        migrations.AddIndex(
            model_name="checkinrecord",
            index=models.Index(
                fields=["his_patient_sync", "status"],
                name="reception_ci_his_status_idx",
            ),
        ),
    ]
