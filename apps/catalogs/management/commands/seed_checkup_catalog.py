import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalogs.models import CheckupCategory, GroupCheckup


def _to_int(value, default=0):
    if value in (None, "", "None"):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Command(BaseCommand):
    help = "Seed danh mục khám từ file JSON."

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True, help="Đường dẫn file JSON nguồn.")
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Xóa toàn bộ dữ liệu catalog hiện có trước khi import.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["path"]).expanduser().resolve()
        if not path.exists():
            raise CommandError(f"Không tìm thấy file JSON: {path}")

        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        items = raw.get("catalog") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            raise CommandError("JSON không đúng định dạng catalog list.")

        if options["clear"]:
            CheckupCategory.objects.all().delete()
            GroupCheckup.objects.all().delete()
            self.stdout.write(self.style.WARNING("Đã xóa dữ liệu catalog cũ."))

        created_groups = 0
        created_categories = 0
        updated_categories = 0

        group_cache = {}

        for index, row in enumerate(items, start=1):
            group_name = (row.get("group") or "Khác").strip()
            group_en = (row.get("group_en") or "").strip()

            if group_name not in group_cache:
                group_obj, group_created = GroupCheckup.objects.get_or_create(
                    name=group_name,
                    defaults={
                        "group_en": group_en,
                        "display_order": index,
                        "is_active": True,
                    },
                )
                if not group_created:
                    dirty = False
                    if group_en and not group_obj.group_en:
                        group_obj.group_en = group_en
                        dirty = True
                    if dirty:
                        group_obj.save(update_fields=["group_en", "updated_at"])
                group_cache[group_name] = group_obj
                if group_created:
                    created_groups += 1

            group_obj = group_cache[group_name]
            item_code = str(row.get("id") or "").strip() or None

            defaults = {
                "group_checkup": group_obj,
                "subgroup_name": (row.get("subgroup") or "").strip(),
                "display_order": _to_int(row.get("stt"), default=index),
                "item_name": (row.get("name") or "").strip(),
                "description": (row.get("description") or "").strip(),
                "price": str(_to_int(row.get("list_price"), default=0)),
                "list_price": _to_int(row.get("list_price"), default=0),
                "price_type": (row.get("price_type") or "standard").strip(),
                "price_male": row.get("price_male"),
                "price_female_single": row.get("price_female_single"),
                "price_female_family": row.get("price_female_family"),
                "for_male": bool(row.get("for_male", True)),
                "for_female_single": bool(row.get("for_female_single", True)),
                "for_female_family": bool(row.get("for_female_family", True)),
                "note": (row.get("note") or "").strip(),
                "is_active": True,
            }

            if item_code:
                obj, created = CheckupCategory.objects.update_or_create(
                    item_code=item_code,
                    defaults=defaults,
                )
            else:
                obj, created = CheckupCategory.objects.update_or_create(
                    group_checkup=group_obj,
                    item_name=defaults["item_name"],
                    subgroup_name=defaults["subgroup_name"],
                    defaults=defaults,
                )

            if created:
                created_categories += 1
            else:
                updated_categories += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed thành công: {created_groups} nhóm, "
                f"{created_categories} danh mục tạo mới, "
                f"{updated_categories} danh mục cập nhật."
            )
        )