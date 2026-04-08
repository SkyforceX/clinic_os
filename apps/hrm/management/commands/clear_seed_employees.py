from django.core.management.base import BaseCommand
from django.db import transaction

from apps.hrm.models import Employee


class Command(BaseCommand):
    help = "Xóa dữ liệu nhân viên đã seed từ Excel (employee_code bắt đầu HRM-XLS-)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Chỉ in ra số lượng sẽ xóa, không thực hiện xóa",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        qs = Employee.objects.filter(employee_code__startswith="HRM-XLS-")
        count = qs.count()

        self.stdout.write(self.style.WARNING(f"Tìm thấy {count} nhân viên seed từ Excel"))

        if dry_run:
            self.stdout.write(self.style.NOTICE("DRY RUN - Không xóa dữ liệu"))
            return

        with transaction.atomic():
            deleted_count, _ = qs.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Đã xóa {deleted_count} bản ghi nhân viên seed")
        )