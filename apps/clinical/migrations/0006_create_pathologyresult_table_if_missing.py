from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0005_pathologyresult_his_patient"),
        ("his_integration", "0001_initial"),
        ("patients", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS clinic_pathologyresult (
                id bigserial PRIMARY KEY,
                patient_id bigint NULL
                    REFERENCES patients_patient(id)
                    DEFERRABLE INITIALLY DEFERRED,
                his_patient_id bigint NULL
                    REFERENCES his_integration_patient_sync(id)
                    DEFERRABLE INITIALLY DEFERRED,
                location varchar(255) NOT NULL,
                file_url varchar(100) NOT NULL,
                result_date date NULL,
                auto_extracted_conclusion text NULL,
                manual_conclusion text NULL,
                evaluation varchar(10) NULL,
                created_at timestamp with time zone NOT NULL,
                updated_at timestamp with time zone NOT NULL
            );
            ALTER TABLE clinic_pathologyresult ALTER COLUMN patient_id DROP NOT NULL;
            ALTER TABLE clinic_pathologyresult ADD COLUMN IF NOT EXISTS his_patient_id bigint NULL;
            CREATE INDEX IF NOT EXISTS clinic_pathologyresult_patient_id_idx
                ON clinic_pathologyresult (patient_id);
            CREATE INDEX IF NOT EXISTS clinic_pathologyresult_his_patient_id_idx
                ON clinic_pathologyresult (his_patient_id);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
