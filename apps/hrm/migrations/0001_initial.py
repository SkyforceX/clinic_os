import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Department ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150, unique=True, verbose_name="Tên phòng ban")),
                ("code", models.CharField(blank=True, max_length=20, unique=True, verbose_name="Mã phòng ban")),
                ("description", models.TextField(blank=True, verbose_name="Mô tả")),
                ("is_active", models.BooleanField(default=True, verbose_name="Đang hoạt động")),
                ("display_order", models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="hrm.department",
                        verbose_name="Phòng ban cấp trên",
                    ),
                ),
            ],
            options={
                "verbose_name": "Phòng ban",
                "verbose_name_plural": "Phòng ban",
                "db_table": "hrm_department",
                "ordering": ["display_order", "name"],
            },
        ),

        # ── Position ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Position",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150, unique=True, verbose_name="Tên chức vụ")),
                ("code", models.CharField(blank=True, max_length=20, unique=True, verbose_name="Mã chức vụ")),
                ("level", models.PositiveSmallIntegerField(default=1, verbose_name="Cấp bậc")),
                ("is_active", models.BooleanField(default=True, verbose_name="Đang hoạt động")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "department",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="positions",
                        to="hrm.department",
                        verbose_name="Phòng ban",
                    ),
                ),
            ],
            options={
                "verbose_name": "Chức vụ",
                "verbose_name_plural": "Chức vụ",
                "db_table": "hrm_position",
                "ordering": ["-level", "name"],
            },
        ),

        # ── Employee ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("employee_code", models.CharField(max_length=20, unique=True, verbose_name="Mã nhân viên")),
                ("full_name", models.CharField(max_length=150, verbose_name="Họ và tên")),
                ("gender", models.CharField(blank=True, max_length=10, verbose_name="Giới tính")),
                ("date_of_birth", models.DateField(blank=True, null=True, verbose_name="Ngày sinh")),
                ("phone", models.CharField(blank=True, max_length=20, verbose_name="Số điện thoại")),
                ("email", models.EmailField(blank=True, verbose_name="Email cá nhân")),
                ("address", models.TextField(blank=True, verbose_name="Địa chỉ thường trú")),
                ("id_card_number", models.CharField(blank=True, max_length=20, verbose_name="Số CCCD / CMND")),
                ("id_card_issued_date", models.DateField(blank=True, null=True, verbose_name="Ngày cấp")),
                ("id_card_issued_by", models.CharField(blank=True, max_length=200, verbose_name="Nơi cấp")),
                ("tax_code", models.CharField(blank=True, max_length=20, verbose_name="Mã số thuế cá nhân")),
                ("social_insurance_code", models.CharField(blank=True, max_length=20, verbose_name="Số BHXH")),
                ("bank_account", models.CharField(blank=True, max_length=30, verbose_name="Số tài khoản ngân hàng")),
                ("bank_name", models.CharField(blank=True, max_length=100, verbose_name="Ngân hàng")),
                ("employment_type", models.CharField(
                    choices=[
                        ("FULLTIME", "Chính thức toàn thời gian"),
                        ("PARTTIME", "Bán thời gian"),
                        ("PROBATION", "Thử việc"),
                        ("CONTRACT", "Hợp đồng có thời hạn"),
                        ("INTERNSHIP", "Thực tập"),
                    ],
                    default="FULLTIME", max_length=20, verbose_name="Loại hình công việc",
                )),
                ("hire_date", models.DateField(blank=True, null=True, verbose_name="Ngày vào làm")),
                ("probation_end_date", models.DateField(blank=True, null=True, verbose_name="Ngày kết thúc thử việc")),
                ("official_date", models.DateField(blank=True, null=True, verbose_name="Ngày chính thức")),
                ("resignation_date", models.DateField(blank=True, null=True, verbose_name="Ngày nghỉ việc")),
                ("status", models.CharField(
                    choices=[
                        ("PROBATION", "Đang thử việc"),
                        ("ACTIVE", "Đang làm việc"),
                        ("RESIGNED", "Đã nghỉ việc"),
                        ("TERMINATED", "Bị chấm dứt"),
                        ("ON_LEAVE", "Đang nghỉ phép dài hạn"),
                    ],
                    db_index=True, default="PROBATION", max_length=20, verbose_name="Trạng thái",
                )),
                ("emergency_contact_name", models.CharField(blank=True, max_length=150, verbose_name="Tên người liên hệ khẩn cấp")),
                ("emergency_contact_phone", models.CharField(blank=True, max_length=20, verbose_name="SĐT khẩn cấp")),
                ("emergency_contact_rel", models.CharField(blank=True, max_length=50, verbose_name="Quan hệ")),
                ("note", models.TextField(blank=True, verbose_name="Ghi chú nội bộ")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="employee_profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Tài khoản hệ thống",
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="employees",
                        to="hrm.department",
                        verbose_name="Phòng ban",
                    ),
                ),
                (
                    "position",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="employees",
                        to="hrm.position",
                        verbose_name="Chức vụ",
                    ),
                ),
                (
                    "direct_manager",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="direct_reports",
                        to="hrm.employee",
                        verbose_name="Quản lý trực tiếp",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_employees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người tạo hồ sơ",
                    ),
                ),
            ],
            options={
                "verbose_name": "Nhân viên",
                "verbose_name_plural": "Nhân viên",
                "db_table": "hrm_employee",
                "ordering": ["full_name"],
                "indexes": [
                    models.Index(fields=["status"], name="hrm_employee_status_idx"),
                    models.Index(fields=["department"], name="hrm_employee_dept_idx"),
                ],
            },
        ),

        # ── PositionGroupMapping ──────────────────────────────────────────────
        migrations.CreateModel(
            name="PositionGroupMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("note", models.CharField(blank=True, max_length=255, verbose_name="Ghi chú")),
                (
                    "position",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_mappings",
                        to="hrm.position",
                        verbose_name="Chức vụ",
                    ),
                ),
                (
                    "django_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="position_mappings",
                        to="auth.group",
                        verbose_name="Django Group",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ánh xạ Chức vụ → Nhóm quyền",
                "verbose_name_plural": "Ánh xạ Chức vụ → Nhóm quyền",
                "db_table": "hrm_position_group_mapping",
                "unique_together": {("position", "django_group")},
            },
        ),

        # ── AccessLog ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AccessLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("action", models.CharField(
                    choices=[
                        ("GRANTED", "Cấp quyền"),
                        ("REVOKED", "Thu hồi quyền"),
                        ("ONBOARD", "Onboard"),
                        ("OFFBOARD", "Offboard"),
                        ("TRANSFER", "Chuyển bộ phận"),
                    ],
                    max_length=20, verbose_name="Hành động",
                )),
                ("note", models.TextField(blank=True, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_logs",
                        to="hrm.employee",
                        verbose_name="Nhân viên",
                    ),
                ),
                (
                    "django_group",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="auth.group",
                        verbose_name="Nhóm quyền",
                    ),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hrm_access_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người thực hiện",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log phân quyền",
                "verbose_name_plural": "Log phân quyền",
                "db_table": "hrm_access_log",
                "ordering": ["-created_at"],
            },
        ),
    ]
