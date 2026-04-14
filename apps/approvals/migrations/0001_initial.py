import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Tạo hai model trung tâm cho hệ thống phê duyệt:
    - ApprovalRequest  : yêu cầu phê duyệt (hỗ trợ 4 loại tài liệu)
    - ApprovalLog      : audit trail immutable

    Phụ thuộc contract.0011 vì cần FK tới PaymentVoucher và ProposalForm.
    """

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contract", "0011_paymentvoucher_proposalform"),
    ]

    operations = [
        # ── ApprovalRequest ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="ApprovalRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "request_type",
                    models.CharField(
                        choices=[
                            ("QUOTATION",       "Báo giá"),
                            ("CONTRACT",        "Hợp đồng"),
                            ("PAYMENT_VOUCHER", "Phiếu thanh toán"),
                            ("PROPOSAL",        "Phiếu đề xuất"),
                        ],
                        db_index=True,
                        max_length=30,
                        verbose_name="Loại tài liệu",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING",  "Chờ duyệt"),
                            ("APPROVED", "Đã duyệt"),
                            ("REJECTED", "Từ chối"),
                            ("RECALLED", "Thu hồi"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                        verbose_name="Trạng thái",
                    ),
                ),
                (
                    "quotation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_requests",
                        to="contract.quotationdraft",
                        verbose_name="Báo giá",
                    ),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_requests",
                        to="contract.contract",
                        verbose_name="Hợp đồng",
                    ),
                ),
                (
                    "payment_voucher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_requests",
                        to="contract.paymentvoucher",
                        verbose_name="Phiếu thanh toán",
                    ),
                ),
                (
                    "proposal",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_requests",
                        to="contract.proposalform",
                        verbose_name="Phiếu đề xuất",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_requests_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người nộp",
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True, verbose_name="Thời gian nộp")),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_requests_reviewed",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người duyệt",
                    ),
                ),
                ("reviewed_at",     models.DateTimeField(blank=True, null=True, verbose_name="Thời gian duyệt")),
                ("requester_note",  models.TextField(blank=True, verbose_name="Ghi chú người nộp")),
                ("reviewer_note",   models.TextField(blank=True, verbose_name="Ghi chú người duyệt")),
            ],
            options={
                "verbose_name": "Yêu cầu phê duyệt",
                "verbose_name_plural": "Yêu cầu phê duyệt",
                "db_table": "approvals_request",
                "ordering": ["-requested_at"],
            },
        ),
        # ── Indexes cho ApprovalRequest ─────────────────────────────────────
        migrations.AddIndex(
            model_name="approvalrequest",
            index=models.Index(fields=["request_type", "status"], name="apr_type_status_idx"),
        ),
        migrations.AddIndex(
            model_name="approvalrequest",
            index=models.Index(fields=["requested_by", "status"], name="apr_requester_status_idx"),
        ),
        # ── ApprovalLog ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ApprovalLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "approval_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="approvals.approvalrequest",
                        verbose_name="Yêu cầu phê duyệt",
                    ),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người thực hiện",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("SUBMITTED", "Nộp phê duyệt"),
                            ("APPROVED",  "Phê duyệt"),
                            ("REJECTED",  "Từ chối"),
                            ("RECALLED",  "Thu hồi"),
                        ],
                        max_length=20,
                        verbose_name="Hành động",
                    ),
                ),
                ("note",       models.TextField(blank=True, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")),
            ],
            options={
                "verbose_name": "Lịch sử phê duyệt",
                "verbose_name_plural": "Lịch sử phê duyệt",
                "db_table": "approvals_log",
                "ordering": ["created_at"],
            },
        ),
    ]
