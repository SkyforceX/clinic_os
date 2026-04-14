import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contract", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        # tasks app: dùng string FK nên migration không cần depend ở đây.
        # Khi tasks app migrate xong, chạy thêm 0002_add_task_fk.py.
    ]

    operations = [
        # ── MeetingSession ────────────────────────────────────────────────
        migrations.CreateModel(
            name="MeetingSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=500, verbose_name="Tiêu đề buổi họp")),
                ("meeting_date", models.DateField(verbose_name="Ngày họp")),
                ("meeting_time", models.TimeField(blank=True, null=True, verbose_name="Giờ bắt đầu")),
                ("location", models.CharField(blank=True, max_length=255, verbose_name="Địa điểm")),
                ("note", models.TextField(blank=True, verbose_name="Ghi chú")),
                ("status", models.CharField(
                    choices=[("OPEN", "OPEN"), ("CLOSED", "CLOSED"), ("SIGNED", "SIGNED"), ("CANCELLED", "CANCELLED")],
                    db_index=True,
                    default="OPEN",
                    max_length=20,
                    verbose_name="Trạng thái",
                )),
                ("current_step", models.PositiveSmallIntegerField(default=1, verbose_name="Bước hiện tại (1–5)")),
                ("closed_at", models.DateTimeField(blank=True, null=True, verbose_name="Thời điểm đóng họp")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("contract", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="meeting_sessions",
                    to="contract.contract",
                    verbose_name="Hợp đồng liên quan",
                )),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="meeting_sessions",
                    to="organizations.company",
                    verbose_name="Doanh nghiệp",
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_meeting_sessions",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người tạo",
                )),
                ("closed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="closed_meeting_sessions",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người đóng họp",
                )),
            ],
            options={
                "verbose_name": "Buổi họp",
                "verbose_name_plural": "Danh sách buổi họp",
                "db_table": "meeting_session",
                "ordering": ["-meeting_date", "-created_at"],
            },
        ),

        # ── MeetingParticipant ────────────────────────────────────────────
        migrations.CreateModel(
            name="MeetingParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department", models.CharField(
                    blank=True, max_length=20,
                    choices=[("kd","Kinh doanh"),("dd","Điều dưỡng / Lâm sàng"),("hc","Hành chính / Vận hành"),("kt","Kế toán / Tài chính"),("it","IT / Hệ thống"),("other","Khác")],
                    verbose_name="Phòng ban đại diện",
                )),
                ("role", models.CharField(
                    choices=[("LEAD","LEAD"),("MEMBER","MEMBER"),("VIEWER","VIEWER")],
                    default="MEMBER", max_length=10, verbose_name="Vai trò",
                )),
                ("can_edit", models.BooleanField(default=True, verbose_name="Được chỉnh sửa trực tiếp")),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="participants",
                    to="meeting.meetingsession",
                    verbose_name="Buổi họp",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="meeting_participations",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người dùng",
                )),
            ],
            options={
                "verbose_name": "Người tham dự",
                "verbose_name_plural": "Danh sách người tham dự",
                "db_table": "meeting_participant",
                "ordering": ["department", "role"],
                "unique_together": {("session", "user")},
            },
        ),

        # ── DeptAssignment ────────────────────────────────────────────────
        migrations.CreateModel(
            name="DeptAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department", models.CharField(
                    choices=[("kd","Kinh doanh"),("dd","Điều dưỡng / Lâm sàng"),("hc","Hành chính / Vận hành"),("kt","Kế toán / Tài chính"),("it","IT / Hệ thống"),("other","Khác")],
                    db_index=True, max_length=20, verbose_name="Phòng ban",
                )),
                ("confirmed", models.BooleanField(default=False, db_index=True, verbose_name="Đã xác nhận")),
                ("confirmed_at", models.DateTimeField(blank=True, null=True, verbose_name="Thời điểm xác nhận")),
                ("notes", models.TextField(blank=True, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("session", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="dept_assignments",
                    to="meeting.meetingsession",
                    verbose_name="Buổi họp",
                )),
                ("lead_user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="led_dept_assignments",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Trưởng phòng / Đại diện",
                )),
                ("confirmed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="confirmed_dept_assignments",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Xác nhận bởi",
                )),
            ],
            options={
                "verbose_name": "Phân công phòng ban",
                "verbose_name_plural": "Phân công phòng ban",
                "db_table": "meeting_dept_assignment",
                "ordering": ["department"],
                "unique_together": {("session", "department")},
            },
        ),

        # ── StaffShift ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="StaffShift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role_in_day", models.CharField(blank=True, max_length=255, verbose_name="Vai trò trong ngày")),
                ("shift", models.CharField(
                    choices=[("AM","AM"),("PM","PM"),("FULL","FULL"),("OFF","OFF")],
                    default="FULL", max_length=5, verbose_name="Ca",
                )),
                ("time_from", models.TimeField(blank=True, null=True, verbose_name="Từ giờ")),
                ("time_to", models.TimeField(blank=True, null=True, verbose_name="Đến giờ")),
                ("confirmed", models.BooleanField(default=True, verbose_name="Đã xác nhận")),
                ("note", models.CharField(blank=True, max_length=255, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("dept_assignment", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="staff_shifts",
                    to="meeting.deptassignment",
                    verbose_name="Phân công phòng ban",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="meeting_staff_shifts",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Nhân viên",
                )),
            ],
            options={
                "verbose_name": "Ca làm việc nhân viên",
                "verbose_name_plural": "Ca làm việc nhân viên",
                "db_table": "meeting_staff_shift",
                "ordering": ["shift", "user__last_name"],
                "unique_together": {("dept_assignment", "user")},
            },
        ),

        # ── MeetingCommitment ─────────────────────────────────────────────
        migrations.CreateModel(
            name="MeetingCommitment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=500, verbose_name="Nội dung cam kết")),
                ("description", models.TextField(blank=True, verbose_name="Mô tả chi tiết")),
                ("deadline", models.DateField(blank=True, null=True, verbose_name="Deadline")),
                ("status", models.CharField(
                    choices=[("OPEN","OPEN"),("DONE","DONE"),("CANCELLED","CANCELLED")],
                    db_index=True, default="OPEN", max_length=20, verbose_name="Trạng thái",
                )),
                ("display_order", models.PositiveIntegerField(default=0, verbose_name="Thứ tự")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("session", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="commitments",
                    to="meeting.meetingsession",
                    verbose_name="Buổi họp",
                )),
                ("dept_assignment", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="commitments",
                    to="meeting.deptassignment",
                    verbose_name="Phòng ban phụ trách",
                )),
                ("assignee", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="meeting_commitments",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người thực hiện",
                )),
                # task FK thêm ở migration 0002 sau khi tasks app sẵn sàng
            ],
            options={
                "verbose_name": "Cam kết trong họp",
                "verbose_name_plural": "Danh sách cam kết",
                "db_table": "meeting_commitment",
                "ordering": ["display_order", "created_at"],
            },
        ),

        # ── MeetingSignature ──────────────────────────────────────────────
        migrations.CreateModel(
            name="MeetingSignature",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department", models.CharField(blank=True, max_length=20, verbose_name="Phòng ban đại diện")),
                ("role_label", models.CharField(blank=True, max_length=100, verbose_name="Chức danh")),
                ("signed_at", models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm ký")),
                ("doc_hash", models.CharField(
                    max_length=64,
                    verbose_name="SHA-256 hash biên bản",
                    help_text="Hash của nội dung biên bản PDF tại thời điểm ký.",
                )),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP address")),
                ("user_agent", models.TextField(blank=True, verbose_name="User agent")),
                ("session", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="signatures",
                    to="meeting.meetingsession",
                    verbose_name="Buổi họp",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="meeting_signatures",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người ký",
                )),
            ],
            options={
                "verbose_name": "Chữ ký biên bản",
                "verbose_name_plural": "Chữ ký biên bản",
                "db_table": "meeting_signature",
                "ordering": ["signed_at"],
                "unique_together": {("session", "user")},
            },
        ),
    ]
