from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from apps.approvals.domain.exceptions import ApprovalDomainError, ApprovalPermissionDenied
from apps.approvals.models import ApprovalRequestType, ApprovalStatus
from apps.approvals.policies import ApprovalPolicy
from apps.approvals.selectors import (
    get_inbox_requests,
    get_my_requests,
    get_request_detail,
)
from apps.approvals.services import approve_request, recall_request, reject_request

LOGIN_URL = "authentication:staff_login"


@login_required(login_url=LOGIN_URL)
def inbox(request):
    """Trang inbox — chỉ Manager."""
    if not ApprovalPolicy.can_view_inbox(request.user):
        raise Http404("Bạn không có quyền truy cập inbox phê duyệt.")

    status_filter = request.GET.get("status", "")
    type_filter   = request.GET.get("type", "")

    requests_qs = get_inbox_requests(
        status_filter=status_filter,
        type_filter=type_filter,
    )

    return render(request, "approvals/staff/inbox.html", {
        "approval_requests":    requests_qs,
        "status_filter":        status_filter,
        "type_filter":          type_filter,
        "status_choices":       ApprovalStatus.choices,
        "type_choices":         ApprovalRequestType.choices,
    })


@login_required(login_url=LOGIN_URL)
def my_requests(request):
    """Danh sách request do chính user nộp."""
    requests_qs = get_my_requests(request.user)
    return render(request, "approvals/staff/my_requests.html", {
        "approval_requests": requests_qs,
    })


@login_required(login_url=LOGIN_URL)
def detail(request, pk: int):
    ar = get_request_detail(pk)
    if ar is None:
        raise Http404("Không tìm thấy yêu cầu phê duyệt.")
    if not ApprovalPolicy.can_view_request(request.user, ar):
        raise Http404("Bạn không có quyền xem yêu cầu này.")

    return render(request, "approvals/staff/detail.html", {
        "ar":          ar,
        "logs":        ar.logs.all(),
        "can_approve": ApprovalPolicy.can_approve(request.user, ar),
        "can_reject":  ApprovalPolicy.can_reject(request.user, ar),
        "can_recall":  ApprovalPolicy.can_recall(request.user, ar),
    })


@login_required(login_url=LOGIN_URL)
@require_POST
def approve(request, pk: int):
    try:
        ar = approve_request.execute(
            approval_request_id=pk,
            actor=request.user,
            reviewer_note=request.POST.get("reviewer_note", "").strip(),
        )
        messages.success(request, f"✅ Đã phê duyệt yêu cầu #{ar.pk}.")
    except ApprovalPermissionDenied as e:
        messages.error(request, str(e))
    except ApprovalDomainError as e:
        messages.error(request, str(e))

    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect("approvals:inbox")


@login_required(login_url=LOGIN_URL)
@require_POST
def reject(request, pk: int):
    try:
        ar = reject_request.execute(
            approval_request_id=pk,
            actor=request.user,
            reviewer_note=request.POST.get("reviewer_note", "").strip(),
        )
        messages.warning(request, f"Đã từ chối yêu cầu #{ar.pk}.")
    except ApprovalPermissionDenied as e:
        messages.error(request, str(e))
    except ApprovalDomainError as e:
        messages.error(request, str(e))
    # Sau từ chối ở lại detail để manager xem log
    return redirect("approvals:detail", pk=pk)


@login_required(login_url=LOGIN_URL)
@require_POST
def recall(request, pk: int):
    try:
        ar = recall_request.execute(
            approval_request_id=pk,
            actor=request.user,
            note=request.POST.get("note", "").strip(),
        )
        messages.info(request, f"Đã thu hồi yêu cầu #{ar.pk}.")
    except ApprovalPermissionDenied as e:
        messages.error(request, str(e))
    except ApprovalDomainError as e:
        messages.error(request, str(e))
    return redirect("approvals:my_requests")
