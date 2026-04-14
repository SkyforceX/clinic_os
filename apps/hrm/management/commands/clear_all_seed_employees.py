from django.core.management.base import BaseCommand
from django.db import transaction

from apps.hrm.models import Employee


class Command(BaseCommand):
    help = "Xóa TOÀN BỘ dữ liệu Employee (DANGER)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Xác nhận xóa toàn bộ dữ liệu",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Chỉ xem số lượng, không xóa",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]
        dry_run = options["dry_run"]

        qs = Employee.objects.all()
        count = qs.count()

        self.stdout.write(self.style.WARNING(f"Tổng số nhân viên: {count}"))

        if dry_run:
            self.stdout.write(self.style.NOTICE("DRY RUN - Không xóa"))
            return

        if not confirm:
            self.stdout.write(
                self.style.ERROR(
                    "Bạn phải thêm --confirm để xóa toàn bộ dữ liệu!"
                )
            )
            return

        with transaction.atomic():
            deleted_count, _ = qs.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Đã xóa {deleted_count} Employee")
        )