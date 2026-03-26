"""
Root-level views của app booking.

Sau refactor:
- Tạo / duyệt / xóa hợp đồng  → apps.contract (contract/web/views/contract_views.py)
- Schedule table / redistribute → apps.scheduling (scheduling/web/views/)
- Patient booking (register, submit, thankyou) → apps.booking.web.views (file này chỉ delegate)

File này giữ lại:
- register_task   — khởi động cron job terminate hợp đồng
- appointment     — form staff tạo lịch hẹn thủ công (còn dùng tạm)
- normalize_str   — utility dùng chung trong app
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from apps.booking.tasks import auto_terminate_contracts
from apps.organizations.models import Company


# ---------------------------------------------------------------------------
# Task management
# ---------------------------------------------------------------------------

def register_task(request):
    """Endpoint thủ công để đăng ký cron job terminate hợp đồng."""
    auto_terminate_contracts(repeat=60 * 60 * 24)
    return HttpResponse("Task auto terminate hợp đồng đã đăng ký chạy hàng ngày!")


# ---------------------------------------------------------------------------
# Staff views
# ---------------------------------------------------------------------------

@login_required(login_url="authentication:staff_login")
def appointment(request):
    """
    Form staff tạo lịch hẹn thủ công (hiển thị danh sách công ty).

    TODO: chuyển hẳn form tạo hợp đồng/lịch hẹn vào contract app
    khi template appointment_form.html đã được refactor.
    """
    companies = Company.objects.all().order_by("-id")
    return render(request, "booking/appointment_form.html", {"companies": companies})


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def normalize_str(value: str) -> str:
    return str(value).strip().lower()
