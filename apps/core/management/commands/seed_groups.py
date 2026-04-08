"""
Management command: seed_groups
================================
Tạo (hoặc cập nhật) toàn bộ nhóm phân quyền chuẩn cho clinic_os.

Chạy khi triển khai lần đầu hoặc sau khi cập nhật cấu hình nhóm:

    python manage.py seed_groups
    python manage.py seed_groups --verbosity 2   # in chi tiết từng permission
    python manage.py seed_groups --dry-run        # xem trước, không lưu DB

Nguyên tắc thiết kế:
  - Idempotent: chạy nhiều lần vẫn an toàn (get_or_create).
  - Group name khớp chính xác với chuỗi được check trong các Policy class
    (ContractPolicy, SchedulingPolicy, PatientPolicy, ApprovalPolicy …).
  - Mỗi group gán Django model-level permissions → dùng được cả ở admin
    và ở view/API nếu cần @permission_required trong tương lai.
  - Superuser luôn bypass mọi kiểm tra; không cần thêm vào group nào.
"""

from __future__ import annotations

import textwrap
from typing import NamedTuple

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction


# ──────────────────────────────────────────────────────────────────────────────
# Cấu hình nhóm
# ──────────────────────────────────────────────────────────────────────────────

class PermSpec(NamedTuple):
    """
    Khai báo gọn một tập permission cho 1 model.

    app_label   : tên Django app (vd. "contract")
    model_name  : tên model viết thường (vd. "quotationdraft")
    actions     : danh sách action: "add" | "change" | "delete" | "view"
                  Dùng "CRUD" làm alias cho tất cả 4 action.
    """
    app_label: str
    model_name: str
    actions: tuple[str, ...]


def _crud(*args):
    """Trả tuple 4 action tiêu chuẩn."""
    return ("add", "change", "delete", "view")


def _read(*args):
    return ("view",)


def _write(*args):
    return ("add", "change", "view")


# ─── Định nghĩa nhóm ──────────────────────────────────────────────────────────
#
# Mỗi entry:  (group_name, description_vi, [PermSpec, ...])
#
# group_name PHẢI khớp chính xác với chuỗi trong Policy classes:
#   - ContractPolicy.MANAGER_GROUP_NAMES   = {"Manager", "Managers"}
#   - ContractPolicy.NURSE_GROUP_NAMES     = {"Nurses"}
#   - ContractPolicy.EXECUTIVE_GROUP_NAMES = {"Executive", "Executives"}
#   - menu.html in_group: "Sales Team", "Managers", "Doctor"
#
# → Tạo "Managers" (canonical, cũng khớp "Manager" nếu cần legacy)
#   và "Executives" (canonical, cũng khớp "Executive")
# ─────────────────────────────────────────────────────────────────────────────

GROUP_CONFIG: list[tuple[str, str, list[PermSpec]]] = [

    # ══════════════════════════════════════════════════════════════════════════
    # 1. MANAGERS – Trưởng phòng / Quản lý
    #    Quyền: phê duyệt, xem toàn bộ, quản trị hệ thống nội bộ
    # ══════════════════════════════════════════════════════════════════════════
    (
        "Managers",
        "Trưởng phòng / Quản lý – Toàn quyền nội bộ, duyệt báo giá & hợp đồng",
        [
            # --- contract app ---
            PermSpec("contract", "contract",                  _crud()),
            PermSpec("contract", "contractserviceline",       _crud()),
            PermSpec("contract", "quotationdraft",            _crud()),
            PermSpec("contract", "quotationline",             _crud()),
            PermSpec("contract", "corporatecontractprofile",  _crud()),
            PermSpec("contract", "bloodcollectionschedule",   _crud()),
            PermSpec("contract", "implementationplan",        _crud()),
            PermSpec("contract", "issueddocument",            _crud()),
            PermSpec("contract", "paymentvoucher",            _crud()),
            PermSpec("contract", "proposalform",              _crud()),
            PermSpec("contract", "contractnumbersequence",    ("view", "change")),

            # --- approvals app ---
            PermSpec("approvals", "approvalrequest", _crud()),
            PermSpec("approvals", "approvallog",     ("view",)),

            # --- organizations app ---
            PermSpec("organizations", "company", _crud()),

            # --- patients app ---
            PermSpec("patients", "patient", _crud()),

            # --- scheduling app ---
            PermSpec("scheduling", "scheduleslot",  _crud()),
            PermSpec("scheduling", "appointment",   _crud()),

            # --- booking app ---
            PermSpec("booking", "appointment",      ("view", "change")),

            # --- quality app ---
            PermSpec("quality", "medicalrecordaudit", _crud()),
            PermSpec("quality", "incidentreport",     _crud()),

            # --- notifications ---
            PermSpec("notifications", "notification", ("view", "change")),
        ],
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # 2. HR ADMIN – Nhân sự (HRM)
    #    Quyền: toàn quyền module hrm (Employee, Department, Position, AccessLog)
    # ══════════════════════════════════════════════════════════════════════════
    (
        "HR Admin",
        "Phòng Nhân sự – Toàn quyền quản lý hồ sơ nhân viên và phân quyền",
        [
            # --- hrm app ---
            PermSpec("hrm", "employee",             _crud()),
            PermSpec("hrm", "department",           _crud()),
            PermSpec("hrm", "position",             _crud()),
            PermSpec("hrm", "positiongroupmapping", _crud()),
            PermSpec("hrm", "accesslog",            ("view",)),

            # --- auth: xem/sửa user để liên kết nhân viên ---
            PermSpec("auth", "user",  ("view", "change")),
            PermSpec("auth", "group", ("view",)),

            # --- notifications ---
            PermSpec("notifications", "notification", ("view",)),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # 3. SALES TEAM – Nhân viên kinh doanh
    #    Quyền: tạo & chỉnh sửa báo giá / hợp đồng, nộp phê duyệt,
    #           quản lý lịch KSK của hợp đồng mình phụ trách, xem khách hàng
    # ══════════════════════════════════════════════════════════════════════════
    (
        "Sales Team",
        "Nhân viên kinh doanh – Tạo báo giá, hợp đồng, đăng ký lịch KSK",
        [
            # --- contract app ---
            PermSpec("contract", "contract",                 _write()),
            PermSpec("contract", "contractserviceline",      _write()),
            PermSpec("contract", "quotationdraft",           _write()),
            PermSpec("contract", "quotationline",            _write()),
            PermSpec("contract", "corporatecontractprofile", _write()),
            PermSpec("contract", "bloodcollectionschedule",  _write()),
            PermSpec("contract", "implementationplan",       _write()),
            PermSpec("contract", "issueddocument",           ("add", "view")),
            PermSpec("contract", "paymentvoucher",           _write()),
            PermSpec("contract", "proposalform",             _write()),

            # --- approvals app ---
            PermSpec("approvals", "approvalrequest", ("add", "view")),  # nộp & xem của mình
            PermSpec("approvals", "approvallog",     ("view",)),

            # --- organizations app ---
            PermSpec("organizations", "company", _write()),

            # --- patients app ---
            PermSpec("patients", "patient", ("view",)),

            # --- scheduling app ---
            PermSpec("scheduling", "scheduleslot", ("view",)),
            PermSpec("scheduling", "appointment",  ("add", "view", "change")),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # 4. DOCTOR – Bác sĩ
    #    Quyền: lâm sàng (kết quả xét nghiệm, nha khoa, dashboard),
    #           xem thông tin bệnh nhân, dùng Sum Assistant
    # ══════════════════════════════════════════════════════════════════════════
    (
        "Doctor",
        "Bác sĩ – Lâm sàng, kết quả xét nghiệm, Sum Assistant",
        [
            # --- clinical app ---
            PermSpec("clinical", "pathologyresult",  ("add", "change", "view")),
            PermSpec("clinical", "dentalrecord",     ("add", "change", "view")),

            # --- patients app ---
            PermSpec("patients", "patient", ("view",)),

            # --- scheduling / appointment: xem lịch bệnh nhân KSK ---
            PermSpec("scheduling", "appointment",  ("view",)),
            PermSpec("scheduling", "scheduleslot", ("view",)),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # 5. NURSES – Y tá / Điều dưỡng
    #    Quyền: đặt lịch & tiếp nhận bệnh nhân, quản lý appointment,
    #           xem danh sách bệnh nhân
    # ══════════════════════════════════════════════════════════════════════════
    (
        "Nurses",
        "Y tá / Điều dưỡng – Tiếp nhận, đặt lịch, quản lý ca KSK",
        [
            # --- booking app ---
            PermSpec("booking", "appointment", ("add", "change", "view")),

            # --- scheduling app ---
            PermSpec("scheduling", "scheduleslot", ("view",)),
            PermSpec("scheduling", "appointment",  ("add", "change", "view")),

            # --- patients app ---
            PermSpec("patients", "patient", ("add", "view")),

            # --- contract: xem lịch để tiếp nhận đúng hợp đồng ---
            PermSpec("contract", "contract",                ("view",)),
            PermSpec("contract", "bloodcollectionschedule", ("view", "change")),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # 6. EXECUTIVES – Ban Giám đốc
    #    Quyền: view-only toàn bộ hợp đồng, báo giá, kế hoạch thực hiện.
    #    Không được tạo, chỉnh sửa, phê duyệt.
    #    (ContractPolicy.EXECUTIVE_GROUP_NAMES = {"Executive", "Executives"})
    # ══════════════════════════════════════════════════════════════════════════
    (
        "Executives",
        "Ban Giám đốc – Xem toàn bộ hợp đồng & báo giá (không chỉnh sửa)",
        [
            # --- contract app ---
            PermSpec("contract", "contract",                 ("view",)),
            PermSpec("contract", "quotationdraft",           ("view",)),
            PermSpec("contract", "corporatecontractprofile", ("view",)),
            PermSpec("contract", "implementationplan",       ("view",)),
            PermSpec("contract", "issueddocument",           ("view",)),
            PermSpec("contract", "paymentvoucher",           ("view",)),
            PermSpec("contract", "proposalform",             ("view",)),

            # --- approvals app ---
            PermSpec("approvals", "approvalrequest", ("view",)),

            # --- organizations app ---
            PermSpec("organizations", "company", ("view",)),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # 7. ACCOUNTANTS – Kế toán / Tài chính
    #    Quyền: xem & xử lý phiếu thanh toán, xem hợp đồng/báo giá để đối chiếu,
    #           không được phê duyệt hợp đồng
    # ══════════════════════════════════════════════════════════════════════════
    (
        "Accountants",
        "Kế toán / Tài chính – Phiếu thanh toán, đối chiếu hợp đồng",
        [
            # --- contract app ---
            PermSpec("contract", "paymentvoucher",           _write()),
            PermSpec("contract", "contract",                 ("view",)),
            PermSpec("contract", "quotationdraft",           ("view",)),
            PermSpec("contract", "corporatecontractprofile", ("view",)),
            PermSpec("contract", "implementationplan",       ("view",)),
            PermSpec("contract", "issueddocument",           ("view",)),

            # --- approvals: nộp phiếu thanh toán để duyệt ---
            PermSpec("approvals", "approvalrequest", ("add", "view")),
            PermSpec("approvals", "approvallog",     ("view",)),

            # --- organizations app ---
            PermSpec("organizations", "company", ("view",)),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # 8. QUALITY – Kiểm soát chất lượng / QA
    #    Quyền: kiểm tra hồ sơ bệnh án, báo cáo sự cố
    # ══════════════════════════════════════════════════════════════════════════
    (
        "Quality",
        "Kiểm soát chất lượng – Kiểm tra HSBA, báo cáo sự cố",
        [
            # --- quality app ---
            PermSpec("quality", "medicalrecordaudit", _crud()),
            PermSpec("quality", "incidentreport",     _crud()),

            # --- patients: xem để đối chiếu ---
            PermSpec("patients", "patient", ("view",)),
        ],
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_permission(app_label: str, model_name: str, action: str) -> Permission | None:
    """
    Trả về Permission object hoặc None nếu model không tồn tại trong DB
    (vd. model chưa migrate hoặc tên sai).
    """
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model_name)
        return Permission.objects.filter(
            content_type=ct,
            codename=f"{action}_{model_name}",
        ).first()
    except ContentType.DoesNotExist:
        return None


def _collect_permissions(specs: list[PermSpec], verbosity: int) -> list[Permission]:
    """Resolve danh sách PermSpec → list[Permission], bỏ qua model chưa có."""
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
        for m in sorted(set(missing)):
            # In ở verbosity 2 để dev biết model nào chưa migrate
            print(f"    [SKIP] {m}  ← model chưa có hoặc chưa migrate")

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Command
# ──────────────────────────────────────────────────────────────────────────────

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
                "⚠  DRY-RUN mode – không có thay đổi nào được lưu.\n"
            ))

        created_groups: list[str] = []
        updated_groups: list[str] = []
        skipped_groups: list[str] = []

        # Bọc toàn bộ trong transaction để rollback nếu dry-run
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

                # Gán permissions
                perms = _collect_permissions(specs, verbosity)
                group.permissions.set(perms)

                if verbosity >= 2 and perms:
                    for p in sorted(perms, key=lambda x: x.codename):
                        self.stdout.write(f"    ✓  {p.content_type.app_label}.{p.codename}")

                if verbosity >= 1:
                    self.stdout.write(f"         → {len(perms)} quyền được gán.\n")

            if dry_run:
                # Rollback mọi thay đổi
                transaction.set_rollback(True)

        # ── Tóm tắt ───────────────────────────────────────────────────────────
        self.stdout.write("─" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"✔  Tạo mới : {len(created_groups)} nhóm  "
            f"({', '.join(created_groups) or '–'})"
        ))
        self.stdout.write(self.style.WARNING(
            f"↻  Cập nhật: {len(updated_groups)} nhóm  "
            f"({', '.join(updated_groups) or '–'})"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n⚠  DRY-RUN – các thay đổi trên ĐÃ BỊ ROLLBACK."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✔  seed_groups hoàn tất. Tất cả nhóm đã sẵn sàng."
            ))

        # ── Hướng dẫn bổ sung ─────────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO(textwrap.dedent("""
            ─────────────────────────────────────────────────────────────────
            Để gán user vào nhóm (ví dụ):
              python manage.py shell -c "
              from django.contrib.auth import get_user_model
              from django.contrib.auth.models import Group
              u = get_user_model().objects.get(username='nguyen.van.a')
              u.groups.add(Group.objects.get(name='Sales Team'))
              "

            Hoặc vào Django Admin → Users → chọn user → Groups.
            ─────────────────────────────────────────────────────────────────
        """)))
