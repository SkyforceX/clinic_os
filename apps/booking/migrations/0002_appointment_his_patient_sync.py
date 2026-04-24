import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0001_initial"),
        ("his_integration", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appointment",
            name="patient",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="appointments",
                to="patients.patient",
                verbose_name="Bệnh nhân",
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="his_patient_sync",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="appointments",
                to="his_integration.hispatientsync",
                verbose_name="Bệnh nhân HIS",
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=("his_patient_sync", "schedule_slot"),
                name="uq_booking_appointment_his_patient_schedule_slot",
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["his_patient_sync", "status"], name="booking_app_his_pat_70e8d1_idx"),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["schedule_slot", "his_patient_sync"], name="booking_app_schedul_f9e85b_idx"),
        ),
    ]
