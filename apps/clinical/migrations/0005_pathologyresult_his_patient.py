import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0004_dentalexamination_his_patient"),
        ("his_integration", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    DO $$
                    BEGIN
                        IF to_regclass('clinic_pathologyresult') IS NOT NULL THEN
                            EXECUTE 'ALTER TABLE clinic_pathologyresult ALTER COLUMN patient_id DROP NOT NULL';
                            EXECUTE 'ALTER TABLE clinic_pathologyresult ADD COLUMN IF NOT EXISTS his_patient_id bigint NULL';
                            EXECUTE 'CREATE INDEX IF NOT EXISTS clinic_pathologyresult_his_patient_id_idx ON clinic_pathologyresult (his_patient_id)';
                            IF NOT EXISTS (
                                SELECT 1
                                FROM pg_constraint
                                WHERE conname = 'clinic_pathologyresult_his_patient_id_fk'
                            ) THEN
                                EXECUTE 'ALTER TABLE clinic_pathologyresult ADD CONSTRAINT clinic_pathologyresult_his_patient_id_fk FOREIGN KEY (his_patient_id) REFERENCES his_integration_patient_sync(id) DEFERRABLE INITIALLY DEFERRED';
                            END IF;
                        END IF;
                    END $$;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="pathologyresult",
                    name="patient",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="clinical_pathology_results",
                        to="patients.patient",
                    ),
                ),
                migrations.AddField(
                    model_name="pathologyresult",
                    name="his_patient",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pathology_results",
                        to="his_integration.hispatientsync",
                        verbose_name="Bệnh nhân HIS",
                    ),
                ),
            ],
        ),
    ]
