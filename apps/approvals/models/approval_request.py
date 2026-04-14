from django.conf import settings
from django.db import models


class ApprovalRequestType(models.TextChoices):
    QUOTATION       = "QUOTATION",       "Báo giá"
    CONTRACT        = "CONTRACT",        "Hợp đồng"
    PAYMENT_VOUCHER = "PAYMENT_VOUCHER", "Phiếu thanh toán"
    PROPOSAL        = "PROPOSAL",        "Phiếu đề xuất"


class ApprovalStatus(models.TextChoices):
    PENDING  = "PENDING",  "Chờ duyệt"
    APPROVED = "APPROVED", "Đã duyệt"
    REJECTED = "REJECTED", "Từ chối"
    RECALLED = "RECALLED", "Thu hồi"


class ApprovalRequest(models.Model):
    """
    Yêu cầu phê duyệt tập trung cho tất cả loại tài liệu trong hệ thống.

    Quy tắc FK: đúng 1 trong 4 FK bên dưới được set (không null),
    còn lại để null. Validation thực hiện ở service layer (submit_for_approval).
    """

    request_type = models.CharField(
        max_length=30,
        choices=ApprovalRequestType.choices,
        db_index=True,
        verbose_name="Loại tài liệu",
    )
    status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
        verbose_name="Trạng thái",
    )

    # ── FK tài liệu (chỉ 1 field được set) ──────────────────────────────────
    quotation = models.ForeignKey(
        "contract.QuotationDraft",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="approval_requests",
        verbose_name="Báo giá",
    )
    contract = models.ForeignKey(
        "contract.Contract",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="approval_requests",
        verbose_name="Hợp đồng",
    )
    payment_voucher = models.ForeignKey(
        "contract.PaymentVoucher",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="approval_requests",
        verbose_name="Phiếu thanh toán",
    )
    proposal = models.ForeignKey(
        "contract.ProposalForm",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="approval_requests",
        verbose_name="Phiếu đề xuất",
    )

    # ── Người thực hiện ─────────────────────────────────────────────────────
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approval_requests_created",
        verbose_name="Người nộp",
    )
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian nộp")

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approval_requests_reviewed",
        verbose_name="Người duyệt",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian duyệt")

    # ── Nội dung gửi phê duyệt ───────────────────────────────────────────────
    submission_title = models.CharField(
        max_length=255, blank=True,
        verbose_name="Tiêu đề trình duyệt",
    )
    submission_body = models.TextField(
        blank=True,
        verbose_name="Nội dung chi tiết (HTML)",
    )

    # ── Ghi chú ngắn (giữ backward compat) ──────────────────────────────────
    requester_note = models.TextField(blank=True, verbose_name="Ghi chú người nộp")
    reviewer_note  = models.TextField(blank=True, verbose_name="Ghi chú người duyệt")

    class Meta:
        db_table = "approvals_request"
        ordering = ["-requested_at"]
        verbose_name = "Yêu cầu phê duyệt"
        verbose_name_plural = "Yêu cầu phê duyệt"
        indexes = [
            models.Index(fields=["request_type", "status"]),
            models.Index(fields=["requested_by", "status"]),
        ]

    def __str__(self):
        doc = self.document_label
        return f"[{self.get_request_type_display()}] {doc} — {self.get_status_display()}"

    # ── Helpers ─────────────────────────────────────────────────────────────

    @property
    def document(self):
        return (
            self.quotation
            or self.contract
            or self.payment_voucher
            or self.proposal
        )

    @property
    def document_url(self) -> str | None:
        """URL truy cập nhanh tài liệu gốc."""
        try:
            from django.urls import reverse
            doc = self.document
            if doc is None:
                return None
            from apps.contract.models import QuotationDraft, Contract, PaymentVoucher, ProposalForm
            if isinstance(doc, QuotationDraft):
                return reverse("contract:quotation_preview", args=[doc.pk])
            if isinstance(doc, Contract):
                return reverse("contract:corporate_contract_detail", args=[doc.pk])
        except Exception:
            pass
        return None

    @property
    def document_label(self) -> str:
        doc = self.document
        if doc is None:
            return f"#{self.pk}"
        return str(doc)

    @property
    def is_pending(self) -> bool:
        return self.status == ApprovalStatus.PENDING

    @property
    def is_approved(self) -> bool:
        return self.status == ApprovalStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.status == ApprovalStatus.REJECTED

    @property
    def is_recalled(self) -> bool:
        return self.status == ApprovalStatus.RECALLED

    @property
    def is_closed(self) -> bool:
        return self.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED)
