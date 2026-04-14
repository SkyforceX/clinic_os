"""
Views POST để nộp báo giá / hợp đồng vào hàng chờ phê duyệt.
Đặt trong contract app vì biết URL của contract, nhưng gọi
sang approvals.services để giữ logic tập trung.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.approvals.domain.exceptions import ApprovalDomainError
from apps.approvals.services.submit_for_approval import execute as submit_for_approval
from apps.contract.models import Contract, QuotationDraft

LOGIN_URL = "authentication:staff_login"


@login_required(login_url=LOGIN_URL)
@require_POST
def submit_quotation_for_approval(request, quotation_id: int):
    """POST /contract/quotations/<id>/submit-approval/"""
    q = get_object_or_404(QuotationDraft, pk=quotation_id)

    try:
        ar = submit_for_approval(
            document=q,
            actor=request.user,
            requester_note=request.POST.get("requester_note", "").strip(),
        )
        messages.success(
            request,
            f"✅ Đã nộp báo giá #{q.pk} để phê duyệt (yêu cầu #{ar.pk}).",
        )
    except ApprovalDomainError as e:
        messages.error(request, str(e))

    # Quay lại preview/edit của báo giá
    return redirect("contract:quotation_preview", quotation_id=q.pk)


@login_required(login_url=LOGIN_URL)
@require_POST
def submit_contract_for_approval(request, contract_id: int):
    """POST /contract/corporate/<id>/submit-approval/"""
    c = get_object_or_404(Contract, pk=contract_id)

    try:
        ar = submit_for_approval(
            document=c,
            actor=request.user,
            requester_note=request.POST.get("requester_note", "").strip(),
        )
        messages.success(
            request,
            f"✅ Đã nộp hợp đồng {c.contract_number or '#'+str(c.pk)} "
            f"để phê duyệt (yêu cầu #{ar.pk}).",
        )
    except ApprovalDomainError as e:
        messages.error(request, str(e))

    return redirect("contract:corporate_contract_print", contract_id=c.pk)
