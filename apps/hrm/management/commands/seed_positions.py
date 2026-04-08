"""
Management command: seed_positions
====================================
Seed dữ liệu chuẩn cho Phòng ban, Chức vụ và PositionGroupMapping
theo cơ cấu thực tế của clinic_os.

Chạy SAU khi seed_groups đã chạy:

    python manage.py seed_groups
    python manage.py seed_positions
    python manage.py seed_positions --dry-run

Khuyến nghị nếu cần làm sạch dữ liệu cũ:
    python manage.py clear_hrm_org_structure --confirm
    python manage.py seed_positions
"""

from __future__ import annotations

import textwrap

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction


# (code, name, parent_code_or_None, display_order)
DEPARTMENTS = [
    ("BGD", "Ban giám đốc", None, 1),
    ("KD", "Phòng Kinh doanh", None, 2),
    ("NS", "Phòng Nhân sự", None, 3),
    ("LS", "Khoa Lâm sàng", None, 4),
    ("XN", "Khoa Xét nghiệm", None, 5),
    ("CDHA", "Khoa Chẩn đoán hình ảnh", None, 6),
    ("VH", "Phòng Vận hành", None, 7),
    ("KT", "Phòng Kế toán", None, 8),
    ("CNTT", "Phòng Công nghệ thông tin", None, 9),
]


# (code, name, department_code, level)
# level: 1=nhân viên, 5=trưởng phòng/khoa, 7=phó giám đốc, 9=giám đốc
POSITIONS = [
    # Ban giám đốc
    ("GD", "Giám đốc", "BGD", 9),
    ("PGD", "Phó giám đốc", "BGD", 7),

    # Phòng Kinh doanh
    ("TPKD", "Trưởng phòng kinh doanh", "KD", 5),
    ("NVKD", "Nhân viên kinh doanh", "KD", 1),

    # Phòng Nhân sự
    ("TPNS", "Trưởng phòng nhân sự", "NS", 5),
    ("NVNS", "Nhân viên Nhân sự", "NS", 1),

    # Khoa Lâm sàng
    ("BSNOI", "Bác sĩ Nội", "LS", 1),
    ("BSNGOAI", "Bác sĩ Ngoại", "LS", 1),
    ("BSSAN", "Bác sĩ Sản", "LS", 1),
    ("BSDALIEU", "Bác sĩ Da liễu", "LS", 1),
    ("BSTMH", "Bác sĩ Tai Mũi Họng", "LS", 1),
    ("BSRHM", "Bác sĩ Răng Hàm Mặt", "LS", 1),
    ("BSMAT", "Bác sĩ Mắt", "LS", 1),
    ("BSGMHS", "Bác sĩ Gây mê hồi sức", "LS", 1),
    ("BSNOISOI", "Bác sĩ Nội soi", "LS", 1),
    ("DD", "Điều dưỡng", "LS", 1),

    # Khoa Xét nghiệm
    ("TPXN", "Trưởng phòng xét nghiệm", "XN", 5),
    ("KTVXN", "Kỹ thuật viên xét nghiệm", "XN", 1),

    # Khoa Chẩn đoán hình ảnh
    ("TPCDHA", "Trưởng khoa CĐHA", "CDHA", 5),
    ("KTVCDHA", "Kỹ thuật viên CĐHA", "CDHA", 1),

    # Phòng Vận hành
    ("TPVH", "Trưởng phòng vận hành", "VH", 5),
    ("TKYK", "Thư ký y khoa", "VH", 1),

    # Phòng Kế toán
    ("KTTRUONG", "Kế toán trưởng", "KT", 5),
    ("KTVIEN", "Kế toán viên", "KT", 1),

    # Phòng CNTT
    ("TPCNTT", "Trưởng phòng CNTT", "CNTT", 5),
    ("NVCNTT", "Nhân viên CNTT", "CNTT", 1),
]


# (position_code, [group_name, ...])
MAPPINGS = [
    ("GD", ["Executives"]),
    ("PGD", ["Executives", "Managers"]),

    ("TPKD", ["Managers", "Sales Team"]),
    ("NVKD", ["Sales Team"]),

    ("TPNS", ["Managers", "HR Admin"]),
    ("NVNS", ["HR Admin"]),

    ("BSNOI", ["Doctor"]),
    ("BSNGOAI", ["Doctor"]),
    ("BSSAN", ["Doctor"]),
    ("BSDALIEU", ["Doctor"]),
    ("BSTMH", ["Doctor"]),
    ("BSRHM", ["Doctor"]),
    ("BSMAT", ["Doctor"]),
    ("BSGMHS", ["Doctor"]),
    ("BSNOISOI", ["Doctor"]),
    ("DD", ["Nurses"]),

    ("TPXN", ["Managers"]),
    ("KTVXN", ["Nurses"]),

    ("TPCDHA", ["Managers"]),
    ("KTVCDHA", ["Nurses"]),

    ("TPVH", ["Managers"]),
    ("TKYK", ["Nurses"]),

    ("KTTRUONG", ["Managers", "Accountants"]),
    ("KTVIEN", ["Accountants"]),

    ("TPCNTT", ["Managers"]),
    ("NVCNTT", []),
]


class Command(BaseCommand):
    help = textwrap.dedent("""\
        Seed Phòng ban, Chức vụ và PositionGroupMapping chuẩn cho clinic_os.
        Chạy sau seed_groups.
    """)

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Xem trước, không lưu vào database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbosity"]

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY-RUN – không lưu.\n"))

        dept_map = {}
        position_map = {}

        with transaction.atomic():
            self.stdout.write("── Phòng ban ──")
            for code, name, parent_code, order in DEPARTMENTS:
                parent = dept_map.get(parent_code) if parent_code else None
                obj, created = self._upsert_dept(code, name, parent, order)
                dept_map[code] = obj
                label = "TẠO" if created else "CẬP NHẬT"
                if verbose >= 1:
                    self.stdout.write(f"  [{label}] {name}")

            self.stdout.write("\n── Chức vụ ──")
            for code, name, dept_code, level in POSITIONS:
                dept = dept_map.get(dept_code)
                obj, created = self._upsert_pos(code, name, dept, level)
                position_map[code] = obj
                label = "TẠO" if created else "CẬP NHẬT"
                if verbose >= 1:
                    self.stdout.write(f"  [{label}] {name}")

            self.stdout.write("\n── PositionGroupMapping ──")
            from apps.hrm.models.access_control import PositionGroupMapping

            PositionGroupMapping.objects.all().delete()

            for pos_code, group_names in MAPPINGS:
                pos = position_map.get(pos_code)
                if not pos:
                    continue

                for gname in group_names:
                    grp = Group.objects.filter(name=gname).first()
                    if not grp:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  [SKIP] Group '{gname}' chưa tồn tại "
                                f"(hãy chạy seed_groups trước)"
                            )
                        )
                        continue

                    PositionGroupMapping.objects.get_or_create(
                        position=pos,
                        django_group=grp,
                    )
                    if verbose >= 1:
                        self.stdout.write(f"  [OK] {pos.name} → {gname}")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("\n✔ seed_positions hoàn tất."))
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY-RUN – đã rollback."))

    @staticmethod
    def _upsert_dept(code, name, parent, order):
        from apps.hrm.models.department import Department

        obj = Department.objects.filter(code=code).first()
        created = False

        if obj is None:
            obj = Department.objects.create(
                code=code,
                name=name,
                parent=parent,
                display_order=order,
                is_active=True,
            )
            created = True
        else:
            obj.name = name
            obj.parent = parent
            obj.display_order = order
            obj.is_active = True
            obj.save(update_fields=["name", "parent", "display_order", "is_active"])

        return obj, created

    @staticmethod
    def _upsert_pos(code, name, dept, level):
        from apps.hrm.models.department import Position

        obj = Position.objects.filter(code=code).first()
        created = False

        if obj is None:
            obj = Position.objects.create(
                code=code,
                name=name,
                department=dept,
                level=level,
                is_active=True,
            )
            created = True
        else:
            obj.name = name
            obj.department = dept
            obj.level = level
            obj.is_active = True
            obj.save(update_fields=["name", "department", "level", "is_active"])

        return obj, created