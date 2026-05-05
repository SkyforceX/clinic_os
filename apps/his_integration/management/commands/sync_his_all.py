from django.core.management.base import BaseCommand

from apps.his_integration.services import (
    SOURCE_HIS_MSSQL,
    SOURCE_LOCAL_PG,
    build_his_sync_steps,
    run_his_sync_step_inline,
)


class Command(BaseCommand):
    help = "Sync all HIS data: patient_types, patients, packages, exam_records, diagnostic_imaging"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-cursor",
            action="store_true",
            help="Reset cursor to 0 before syncing",
        )
        parser.add_argument(
            "--patient-batch-size",
            type=int,
            default=500,
            help="Batch size for patient sync",
        )
        parser.add_argument(
            "--exam-batch-size",
            type=int,
            default=300,
            help="Batch size for exam record sync",
        )
        parser.add_argument(
            "--source",
            choices=[SOURCE_HIS_MSSQL, SOURCE_LOCAL_PG],
            default=SOURCE_HIS_MSSQL,
            help="Nguồn sync: HIS MSSQL thật hoặc local PostgreSQL test",
        )

    def handle(self, *args, **options):
        steps = build_his_sync_steps(
            sync_type="all",
            reset_cursor=options["reset_cursor"],
            patient_batch_size=options["patient_batch_size"],
            exam_batch_size=options["exam_batch_size"],
            source=options["source"],
        )

        self.stdout.write(
            self.style.WARNING(f"Starting full HIS sync from source={options['source']}...")
        )

        for index, step in enumerate(steps, start=1):
            self.stdout.write(f"{index}/{len(steps)}: Sync {step.label}...")
            result = run_his_sync_step_inline(step)

            if result.successful():
                self.stdout.write(self.style.SUCCESS(f"Done: {step.label}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed: {step.label}: {result.result}"))

        self.stdout.write(self.style.SUCCESS("\nFull HIS sync completed."))
