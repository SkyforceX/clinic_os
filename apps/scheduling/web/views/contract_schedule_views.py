from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.selectors.schedule_matrix import build_contract_schedule_matrix
from apps.scheduling.services.contract_lifecycle import redistribute_contract_slots


@login_required(login_url="authentication:staff_login")
def schedule_table(request):
    if not SchedulingPolicy.can_view_schedule_table(request.user):
        messages.error(request, "Bạn không có quyền xem bảng lịch khám.")
        return redirect("authentication:staff_login")

    context = build_contract_schedule_matrix(actor=request.user)
    return render(request, "booking/staff/schedule_table.html", context)


@login_required(login_url="authentication:staff_login")
def redistribute_slots(request, contract_id):
    try:
        redistribute_contract_slots(actor=request.user, contract_id=contract_id)
        messages.success(request, "Phân bổ lại slot thành công.")
    except PermissionError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Lỗi khi phân bổ lại slot: {exc}")

    return redirect("scheduling:schedule_table")