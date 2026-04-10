from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.clinical.data.tooth_notations import TOOTH_NOTATIONS
from apps.clinical.models import ToothNotation


class Command(BaseCommand):
    help = "Seed dữ liệu tooth notations cho app clinical"

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Xóa các notation trong DB không còn nằm trong dữ liệu nguồn",
        )

    def _table_exists(self, table_name: str) -> bool:
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
        return table_name in tables

    def _validate_item(self, item, index: int):
        if not isinstance(item, dict):
            raise CommandError(
                f"Dòng seed thứ {index} không phải dict: {item!r}"
            )

        required_keys = {"code", "description_vi", "description_en"}
        missing = required_keys - set(item.keys())
        if missing:
            raise CommandError(
                f"Dòng seed thứ {index} thiếu key {sorted(missing)}: {item!r}"
            )

        extra = set(item.keys()) - required_keys
        if extra:
            raise CommandError(
                f"Dòng seed thứ {index} có key thừa {sorted(extra)}: {item!r}"
            )

    @transaction.atomic
    def handle(self, *args, **options):
        prune = options["prune"]
        table_name = ToothNotation._meta.db_table

        if not self._table_exists(table_name):
            raise CommandError(f'Bảng "{table_name}" chưa tồn tại. Hãy migrate trước.')

        created_count = 0
        updated_count = 0

        for index, item in enumerate(TOOTH_NOTATIONS, start=1):
            self._validate_item(item, index)

            obj, created = ToothNotation.objects.update_or_create(
                code=str(item["code"]).strip(),
                defaults={
                    "description_vi": str(item["description_vi"]).strip(),
                    "description_en": str(item["description_en"]).strip(),
                },
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"[CREATED] {obj.code} - {obj.description_vi}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"[UPDATED] {obj.code} - {obj.description_vi}"))

        deleted_count = 0
        if prune:
            source_codes = {str(item["code"]).strip() for item in TOOTH_NOTATIONS}
            qs = ToothNotation.objects.exclude(code__in=source_codes)
            deleted_count = qs.count()
            if deleted_count:
                qs.delete()
                self.stdout.write(self.style.ERROR(f"[DELETED] {deleted_count} notation(s) not in source"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed tooth notations completed."))
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Updated: {updated_count}")
        self.stdout.write(f"Deleted: {deleted_count}")
        self.stdout.write(f"Total source records: {len(TOOTH_NOTATIONS)}")