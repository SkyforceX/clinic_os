"""
Management command: seed_groups
================================
Tạo (hoặc cập nhật) toàn bộ nhóm phân quyền chuẩn cho clinic_os.

Chạy khi triển khai lần đầu hoặc sau khi cập nhật cấu hình nhóm:

    python manage.py seed_groups
    python manage.py seed_groups --verbosity 2   # in chi tiết từng permission
    python manage.py seed_groups --dry-run       # xem trước, không lưu DB

Nguyên tắc thiết kế:
  - Idempotent: chạy nhiều lần vẫn an toàn (get_or_create).
  - Group name khớp chính xác với chuỗi dùng trong seed_positions, Policy classes,
    menu, implementation workflow…
  - Mỗi group gán Django model-level permissions để dùng được cả ở admin
    và ở view/API nếu cần.
  - Superuser luôn bypass mọi kiểm tra; không cần thêm vào group nào.
"""

from __future__ import annotations

import textwrap
from typing import NamedTuple

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction


class PermSpec(NamedTuple):
    app_label: str
    model_name: str
    actions: tuple[str, ...]


def _crud():
    return ("add", "change", "delete", "view")


def _read():
    return ("view",)


def _write():
    return ("add", "change", "view")


GROUP_CONFIG: list[tuple[str, str, list[PermSpec]]] = [
    (
        "Managers",
        "Trưởng phòng / Quản lý – Toàn quyền nội bộ, duyệt báo giá & hợp đồng",
        [
            # contract
            PermSpec("contract", "contract", _crud()),
            PermSpec("contract", "contractserviceline", _crud()),
            PermSpec("contract", "quotationdraft", _crud()),
            PermSpec("contract", "quotationline", _crud()),
            PermSpec("contract", "corporatecontractprofile", _crud()),
            PermSpec("contract", "bloodcollectionschedule", _crud()),
            PermSpec("contract", "implementationplan", _crud()),
            PermSpec("contract", "issueddocument", _crud()),
            PermSpec("contract", "paymentvoucher", _crud()),
            PermSpec("contract", "proposalform", _crud()),
            PermSpec("contract", "contractnumbersequence", ("view", "change")),

            # approvals
            PermSpec("approvals", "approvalrequest", _crud()),
            PermSpec("approvals", "approvallog", ("view",)),

            # organizations
            PermSpec("organizations", "company", _crud()),

            # patients
            PermSpec("patients", "patient", _crud()),

            # scheduling
            PermSpec("scheduling", "scheduleslot", _crud()),
            PermSpec("scheduling", "appointment", _crud()),

            # booking
            PermSpec("booking", "appointment", ("view", "change")),

            # quality
            PermSpec("quality", "medicalrecordaudit", _crud()),
            PermSpec("quality", "incidentreport", _crud()),

            # hrm
            PermSpec("hrm", "employee", ("view",)),
            PermSpec("hrm", "department", ("view",)),
            PermSpec("hrm", "position", ("view",)),

            # notifications
            PermSpec("notifications", "notification", ("view", "change")),
        ],
    ),

    (
        "HR Admins",
        "Phòng Nhân sự – Toàn quyền quản lý hồ sơ nhân viên và phân quyền",
        [
            # hrm
            PermSpec("hrm", "employee", _crud()),
            PermSpec("hrm", "department", _crud()),
            PermSpec("hrm", "position", _crud()),
            PermSpec("hrm", "positiongroupmapping", _crud()),
            PermSpec("hrm", "accesslog", ("view",)),

            # auth
            PermSpec("auth", "user", ("view", "change")),
            PermSpec("auth", "group", ("view",)),

            # notifications
            PermSpec("notifications", "notification", ("view",)),
        ],
    ),

    (
        "Sales Team",
        "Nhân viên kinh doanh – Tạo báo giá, hợp đồng, đăng ký lịch KSK",
        [
            # contract
            PermSpec("contract", "contract", _write()),
            PermSpec("contract", "contractserviceline", _write()),
            PermSpec("contract", "quotationdraft", _write()),
            PermSpec("contract", "quotationline", _write()),
            PermSpec("contract", "corporatecontractprofile", _write()),
            PermSpec("contract", "bloodcollectionschedule", _write()),
            PermSpec("contract", "implementationplan", _write()),
            PermSpec("contract", "issueddocument", ("add", "view")),
            PermSpec("contract", "paymentvoucher", _write()),
            PermSpec("contract", "proposalform", _write()),

            # approvals
            PermSpec("approvals", "approvalrequest", ("add", "view")),
            PermSpec("approvals", "approvallog", ("view",)),

            # organizations
            PermSpec("organizations", "company", _write()),

            # patients
            PermSpec("patients", "patient", ("view",)),

            # scheduling
            PermSpec("scheduling", "scheduleslot", ("view",)),
            PermSpec("scheduling", "appointment", ("add", "view", "change")),
        ],
    ),

    (
        "Doctors",
        "Bác sĩ – Lâm sàng, kết quả xét nghiệm, Sum Assistant",
        [
            # clinical
            PermSpec("clinical", "pathologyresult", ("add", "change", "view")),
            PermSpec("clinical", "dentalrecord", ("add", "change", "view")),

            # patients
            PermSpec("patients", "patient", ("view",)),

            # scheduling
            PermSpec("scheduling", "appointment", ("view",)),
            PermSpec("scheduling", "scheduleslot", ("view",)),
        ],
    ),

    (
        "Nurses",
        "Điều dưỡng / Y tá / Thư ký y khoa – Tiếp nhận, đặt lịch, quản lý ca KSK",
        [
            # booking
            PermSpec("booking", "appointment", ("add", "change", "view")),

            # scheduling
            PermSpec("scheduling", "scheduleslot", ("view",)),
            PermSpec("scheduling", "appointment", ("add", "change", "view")),

            # patients
            PermSpec("patients", "patient", ("add", "view")),

            # contract
            PermSpec("contract", "contract", ("view",)),
            PermSpec("contract", "bloodcollectionschedule", ("view", "change")),
            PermSpec("contract", "implementationplan", ("view",)),
        ],
    ),

    (
        "Executives",
        "Ban Giám đốc – Xem toàn bộ hợp đồng & báo giá (không chỉnh sửa)",
        [
            # contract
            PermSpec("contract", "contract", ("view",)),
            PermSpec("contract", "quotationdraft", ("view",)),
            PermSpec("contract", "corporatecontractprofile", ("view",)),
            PermSpec("contract", "implementationplan", ("view",)),
            PermSpec("contract", "issueddocument", ("view",)),
            PermSpec("contract", "paymentvoucher", ("view",)),
            PermSpec("contract", "proposalform", ("view",)),

            # approvals
            PermSpec("approvals", "approvalrequest", ("view",)),
            PermSpec("approvals", "approvallog", ("view",)),

            # organizations
            PermSpec("organizations", "company", ("view",)),
        ],
    ),

    (
        "Accountants",
        "Kế toán / Tài chính – Phiếu thanh toán, đối chiếu hợp đồng",
        [
            # contract
            PermSpec("contract", "paymentvoucher", _write()),
            PermSpec("contract", "contract", ("view",)),
            PermSpec("contract", "quotationdraft", ("view",)),
            PermSpec("contract", "corporatecontractprofile", ("view",)),
            PermSpec("contract", "implementationplan", ("view",)),
            PermSpec("contract", "issueddocument", ("view",)),

            # approvals
            PermSpec("approvals", "approvalrequest", ("add", "view")),
            PermSpec("approvals", "approvallog", ("view",)),

            # organizations
            PermSpec("organizations", "company", ("view",)),
        ],
    ),

    (
        "Lab Technicians",
        "Kỹ thuật viên xét nghiệm",
        [
            PermSpec("patients", "patient", ("view",)),
            PermSpec("scheduling", "appointment", ("view",)),
            PermSpec("scheduling", "scheduleslot", ("view",)),
            PermSpec("contract", "contract", ("view",)),
            PermSpec("contract", "implementationplan", ("view",)),
        ],
    ),

    (
        "Imaging Technicians",
        "Kỹ thuật viên chẩn đoán hình ảnh",
        [
            PermSpec("patients", "patient", ("view",)),
            PermSpec("scheduling", "appointment", ("view",)),
            PermSpec("scheduling", "scheduleslot", ("view",)),
            PermSpec("contract", "contract", ("view",)),
            PermSpec("contract", "implementationplan", ("view",)),
        ],
    ),

    (
        "Operations Team",
        "Phòng Vận hành – Theo dõi và phối hợp triển khai",
        [
            PermSpec("contract", "contract", ("view",)),
            PermSpec("contract", "bloodcollectionschedule", ("view", "change")),
            PermSpec("contract", "implementationplan", ("view",)),
            PermSpec("patients", "patient", ("view",)),
            PermSpec("scheduling", "scheduleslot", ("view", "change")),
            PermSpec("scheduling", "appointment", ("view", "change")),
        ],
    ),

    (
        "IT Staff",
        "Phòng CNTT",
        [
            PermSpec("hrm", "employee", ("view",)),
            PermSpec("hrm", "department", ("view",)),
            PermSpec("hrm", "position", ("view",)),
            PermSpec("notifications", "notification", ("view",)),
        ],
    ),

    (
        "Customer Service Team",
        "Phòng Chăm sóc khách hàng – Theo dõi khách hàng và phối hợp triển khai",
        [
            PermSpec("patients", "patient", ("view", "change")),
            PermSpec("organizations", "company", ("view",)),
            PermSpec("contract", "contract", ("view",)),
            PermSpec("contract", "corporatecontractprofile", ("view",)),
            PermSpec("contract", "implementationplan", ("view",)),
            PermSpec("scheduling", "appointment", ("view",)),
        ],
    ),

    (
        "Quality",
        "Kiểm soát chất lượng – Kiểm tra HSBA, báo cáo sự cố",
        [
            PermSpec("quality", "medicalrecordaudit", _crud()),
            PermSpec("quality", "incidentreport", _crud()),
            PermSpec("patients", "patient", ("view",)),
        ],
    ),
]


def _get_permission(app_label: str, model_name: str, action: str) -> Permission | None:
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model_name)
        return Permission.objects.filter(
            content_type=ct,
            codename=f"{action}_{model_name}",
        ).first()
    except ContentType.DoesNotExist:
        return None


def _collect_permissions(specs: list[PermSpec], verbosity: int) -> list[Permission]:
    result: list[Permission] = []
    missing: list[str] = []

    for spec in specs:
        for action in spec.actions:
            perm = _get_permission(spec.app_label, spec.model_name, action)
            if perm:
                result.append(perm)
            else:
                missing.append(f"{spec.app_label}.{action}_{spec.model_name}")

    if missing and verbosity >= 2:
        for item in sorted(set(missing)):
            print(f"    [SKIP] {item}  ← model chưa có hoặc chưa migrate")

    return result


class Command(BaseCommand):
    help = textwrap.dedent("""\
        Seed nhóm phân quyền chuẩn cho clinic_os.
        Chạy khi deploy lần đầu hoặc sau khi thay đổi cấu hình nhóm.
        An toàn để chạy nhiều lần (idempotent).
    """)

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Xem trước thay đổi, không lưu vào database.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        verbosity: int = options["verbosity"]

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠ DRY-RUN mode – không có thay đổi nào được lưu.\n"
            ))

        created_groups: list[str] = []
        updated_groups: list[str] = []

        with transaction.atomic():
            for group_name, description, specs in GROUP_CONFIG:
                group, created = Group.objects.get_or_create(name=group_name)

                if created:
                    created_groups.append(group_name)
                    action_label = "TẠO MỚI"
                    style = self.style.SUCCESS
                else:
                    updated_groups.append(group_name)
                    action_label = "CẬP NHẬT"
                    style = self.style.WARNING

                if verbosity >= 1:
                    self.stdout.write(style(f"[{action_label}] {group_name}"))
                    self.stdout.write(f"         {description}")

                perms = _collect_permissions(specs, verbosity)
                group.permissions.set(perms)

                if verbosity >= 2 and perms:
                    for perm in sorted(perms, key=lambda x: x.codename):
                        self.stdout.write(f"    ✓ {perm.content_type.app_label}.{perm.codename}")

                if verbosity >= 1:
                    self.stdout.write(f"         → {len(perms)} quyền được gán.\n")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("─" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"✔ Tạo mới : {len(created_groups)} nhóm ({', '.join(created_groups) or '–'})"
        ))
        self.stdout.write(self.style.WARNING(
            f"↻ Cập nhật: {len(updated_groups)} nhóm ({', '.join(updated_groups) or '–'})"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n⚠ DRY-RUN – các thay đổi trên ĐÃ BỊ ROLLBACK."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✔ seed_groups hoàn tất. Tất cả nhóm đã sẵn sàng."
            ))

        self.stdout.write(self.style.HTTP_INFO(textwrap.dedent("""
            ─────────────────────────────────────────────────────────────────
            Chạy tiếp:
              python manage.py seed_groups
              python manage.py seed_positions

            Ví dụ gán user vào group:
              python manage.py shell -c "
              from django.contrib.auth import get_user_model
              from django.contrib.auth.models import Group
              u = get_user_model().objects.get(username='nguyen.van.a')
              u.groups.add(Group.objects.get(name='Sales Team'))
              "
            ─────────────────────────────────────────────────────────────────
        """)))