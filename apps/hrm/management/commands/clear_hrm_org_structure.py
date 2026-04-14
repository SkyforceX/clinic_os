from django.core.management.base import BaseCommand
from django.db import transaction

from apps.hrm.models import Department, Employee, Position, PositionGroupMapping


class Command(BaseCommand):
    help = "Xóa toàn bộ cơ cấu phòng ban / chức vụ / mapping của HRM để seed lại dữ liệu mới"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Xác nhận thực hiện xóa dữ liệu",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Chỉ xem trước số lượng sẽ xóa, không thực hiện xóa",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]
        dry_run = options["dry_run"]

        department_count = Department.objects.count()
        position_count = Position.objects.count()
        mapping_count = PositionGroupMapping.objects.count()
        employee_linked_count = Employee.objects.filter(
            department__isnull=False
        ).count() + Employee.objects.filter(position__isnull=False).count()

        self.stdout.write(self.style.WARNING("Chuẩn bị reset cơ cấu HRM:"))
        self.stdout.write(f"- Department: {department_count}")
        self.stdout.write(f"- Position: {position_count}")
        self.stdout.write(f"- PositionGroupMapping: {mapping_count}")
        self.stdout.write(f"- Liên kết Employee.department / Employee.position đang dùng: {employee_linked_count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - không xóa dữ liệu"))
            return

        if not confirm:
            self.stdout.write(
                self.style.ERROR("Bạn phải thêm --confirm để thực hiện xóa.")
            )
            return

        with transaction.atomic():
            # Gỡ liên kết trước để tránh lỗi FK
            Employee.objects.exclude(department__isnull=True).update(department=None)
            Employee.objects.exclude(position__isnull=True).update(position=None)

            mapping_deleted, _ = PositionGroupMapping.objects.all().delete()
            position_deleted, _ = Position.objects.all().delete()
            department_deleted, _ = Department.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Đã xóa xong cơ cấu HRM.\n"
                f"- Mapping đã xóa: {mapping_deleted}\n"
                f"- Position đã xóa: {position_deleted}\n"
                f"- Department đã xóa: {department_deleted}"
            )
        )