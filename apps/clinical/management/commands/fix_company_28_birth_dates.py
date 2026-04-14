from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import Patient


class Command(BaseCommand):
    help = (
        "Sửa ngày sinh bị đảo mm/dd/yyyy cho bệnh nhân thuộc company_id=28. "
        "Quy ước: mọi record có day <= 12 đều bị sai và sẽ được đảo day/month."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Chỉ preview, không ghi vào DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        company_id = 28

        qs = (
            Patient.objects
            .filter(company_id=company_id, ngay_sinh__isnull=False)
            .order_by("id")
        )

        total = qs.count()
        candidates = []
        skipped = 0
        invalid = 0

        for patient in qs.iterator():
            old_date = patient.ngay_sinh

            # Rule nghiệp vụ đã xác nhận:
            # chỉ cần day <= 12 là đang sai, phải đảo lại
            if old_date.day <= 12:
                try:
                    new_date = date(
                        year=old_date.year,
                        month=old_date.day,
                        day=old_date.month,
                    )
                    candidates.append((patient, old_date, new_date))
                except ValueError:
                    invalid += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"INVALID | id={patient.id} | ma_bn={patient.ma_bn} | "
                            f"ho_ten={patient.ho_ten} | old={old_date:%d/%m/%Y}"
                        )
                    )
            else:
                skipped += 1

        self.stdout.write(f"Tổng record company_id=28: {total}")
        self.stdout.write(f"Sẽ sửa (day <= 12): {len(candidates)}")
        self.stdout.write(f"Bỏ qua (day > 12): {skipped}")
        self.stdout.write(f"Lỗi không đảo được: {invalid}")

        if not candidates:
            self.stdout.write(self.style.WARNING("Không có record nào cần sửa."))
            return

        self.stdout.write("\nPreview:")
        for patient, old_date, new_date in candidates[:100]:
            self.stdout.write(
                f"- id={patient.id} | {patient.ma_bn} | {patient.ho_ten} | "
                f"{old_date:%d/%m/%Y} -> {new_date:%d/%m/%Y}"
            )

        if len(candidates) > 100:
            self.stdout.write(f"... còn {len(candidates) - 100} record nữa")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN: chưa ghi thay đổi vào DB."))
            return

        with transaction.atomic():
            for patient, _old_date, new_date in candidates:
                patient.ngay_sinh = new_date
                patient.save(update_fields=["ngay_sinh"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nĐã cập nhật {len(candidates)} record cho company_id=28."
            )
        )