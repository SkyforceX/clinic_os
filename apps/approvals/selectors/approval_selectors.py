from apps.approvals.models import ApprovalRequest, ApprovalStatus


def get_inbox_requests(status_filter="", type_filter=""):
    """Tất cả requests cho trang inbox manager, có filter."""
    qs = (
        ApprovalRequest.objects
        .select_related(
            "requested_by",
            "reviewed_by",
            "quotation",
            "contract",
            "payment_voucher",
            "proposal",
        )
        .prefetch_related("logs__actor")
        .order_by("-requested_at")
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(request_type=type_filter)
    return qs


def get_my_requests(user):
    """Requests do user này nộp (mọi trạng thái)."""
    return (
        ApprovalRequest.objects
        .filter(requested_by=user)
        .select_related("reviewed_by", "quotation", "contract", "payment_voucher", "proposal")
        .order_by("-requested_at")
    )


def get_request_detail(pk: int):
    return (
        ApprovalRequest.objects
        .select_related(
            "requested_by",
            "reviewed_by",
            "quotation",
            "contract",
            "payment_voucher",
            "proposal",
        )
        .prefetch_related("logs__actor")
        .filter(pk=pk)
        .first()
    )


def count_pending():
    return ApprovalRequest.objects.filter(status=ApprovalStatus.PENDING).count()
