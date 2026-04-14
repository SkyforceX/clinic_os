# Generated for clinic_os — bước 1 hệ thống phê duyệt

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Tạo hai model mới: PaymentVoucher và ProposalForm trong contract app."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contract", "0010_quotationdraft_status"),
    ]

    operations = [
        # ── PaymentVoucher ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="PaymentVoucher",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_vouchers",
                        to="contract.contract",
                        verbose_name="Hợp đồng",
                    ),
                ),
                (
                    "voucher_type",
                    models.CharField(
                        choices=[
                            ("DEPOSIT",    "Đặt cọc"),
                            ("SETTLEMENT", "Quyết toán"),
                            ("OTHER",      "Khác"),
                        ],
                        default="DEPOSIT",
                        max_length=20,
                        verbose_name="Loại phiếu",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT",     "Nháp"),
                            ("SUBMITTED", "Chờ duyệt"),
                            ("APPROVED",  "Đã duyệt"),
                            ("PAID",      "Đã thanh toán"),
                            ("CANCELLED", "Hủy"),
                        ],
                        db_index=True,
                        default="DRAFT",
                        max_length=20,
                        verbose_name="Trạng thái",
                    ),
                ),
                ("amount",       models.BigIntegerField(verbose_name="Số tiền (VND)")),
                ("amount_words", models.CharField(blank=True, max_length=500, verbose_name="Số tiền bằng chữ")),
                ("due_date",     models.DateField(blank=True, null=True, verbose_name="Hạn thanh toán")),
                ("paid_at",      models.DateField(blank=True, null=True, verbose_name="Ngày đã thanh toán")),
                ("note",         models.TextField(blank=True, verbose_name="Ghi chú")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_payment_vouchers",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người tạo",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Phiếu thanh toán",
                "verbose_name_plural": "Phiếu thanh toán",
                "db_table": "contract_payment_voucher",
                "ordering": ["-created_at"],
            },
        ),
        # ── ProposalForm ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ProposalForm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proposals",
                        to="contract.contract",
                        verbose_name="Hợp đồng liên quan",
                    ),
                ),
                (
                    "proposal_type",
                    models.CharField(
                        choices=[
                            ("PRICE_CHANGE", "Thay đổi giá"),
                            ("SCOPE_CHANGE", "Thay đổi phạm vi dịch vụ"),
                            ("EXTENSION",    "Gia hạn hợp đồng"),
                            ("DISCOUNT",     "Điều chỉnh chiết khấu"),
                            ("OTHER",        "Khác"),
                        ],
                        max_length=30,
                        verbose_name="Loại đề xuất",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT",     "Nháp"),
                            ("SUBMITTED", "Chờ duyệt"),
                            ("APPROVED",  "Đã duyệt"),
                            ("EXECUTED",  "Đã thực hiện"),
                            ("REJECTED",  "Từ chối"),
                            ("CANCELLED", "Hủy"),
                        ],
                        db_index=True,
                        default="DRAFT",
                        max_length=20,
                        verbose_name="Trạng thái",
                    ),
                ),
                ("title",   models.CharField(max_length=255, verbose_name="Tiêu đề")),
                ("content", models.TextField(verbose_name="Nội dung đề xuất")),
                ("amount",  models.BigIntegerField(blank=True, null=True, verbose_name="Giá trị tài chính liên quan (VND)")),
                ("note",    models.TextField(blank=True, verbose_name="Ghi chú")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_proposals",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người tạo",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Phiếu đề xuất",
                "verbose_name_plural": "Phiếu đề xuất",
                "db_table": "contract_proposal_form",
                "ordering": ["-created_at"],
            },
        ),
    ]
