from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.booking.tasks import auto_terminate_contracts
from apps.organizations.models import Company
from apps.scheduling.web.views.contract_schedule_views import (
    redistribute_slots as scheduling_redistribute_slots,
    schedule_table as scheduling_schedule_table,
)
from apps.scheduling.web.views.public_booking_views import (
    register_schedule as scheduling_register_schedule,
    show_thank_you as scheduling_show_thank_you,
    submit_registration as scheduling_submit_registration,
)

from .models import BloodCollectionInfo, HealthContract


def register_task(request):
    auto_terminate_contracts(repeat=60 * 60 * 24)
    return HttpResponse("Task auto terminate hợp đồng đã đăng ký chạy hàng ngày!")


@login_required(login_url="authentication:staff_login")
def appointment(request):
    companies = Company.objects.all().order_by("-id")
    return render(request, "booking/appointment_form.html", {"companies": companies})


def get_next_contract_number():
    year = datetime.now().year
    contracts = HealthContract.objects.filter(contract_number__endswith=f"/VMD-KD/{year}")
    numbers = set()

    for contract in contracts:
        try:
            number = int(str(contract.contract_number).split("/")[0])
            numbers.add(number)
        except Exception:
            continue

    next_number = 1
    while next_number in numbers:
        next_number += 1

    return f"{next_number}/VMD-KD/{year}"


@login_required(login_url="authentication:staff_login")
@csrf_exempt
def save_appointment(request):
    if request.method != "POST":
        return redirect("contract:contract_list")

    company_id = request.POST.get("company_id")
    employee_count = int(request.POST.get("employee_count") or 0)
    start_date_raw = request.POST.get("start_date")
    end_date_raw = request.POST.get("end_date")
    note = request.POST.get("note")

    if not company_id:
        messages.error(request, "Thiếu công ty.")
        return redirect("contract:contract_list")

    if not start_date_raw or not end_date_raw:
        messages.error(request, "Thiếu ngày bắt đầu hoặc ngày kết thúc.")
        return redirect("contract:contract_list")

    try:
        start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Ngày bắt đầu/kết thúc không hợp lệ.")
        return redirect("contract:contract_list")

    company = get_object_or_404(Company, pk=company_id)
    contract_number = get_next_contract_number()

    try:
        with transaction.atomic():
            contract = HealthContract.objects.create(
                company=company,
                contract_number=contract_number,
                employee_count=employee_count,
                start_date=start_date,
                end_date=end_date,
                note=note,
                created_by=request.user,
            )

            dates = request.POST.getlist("blood_collection_date[]")
            locations = request.POST.getlist("blood_location[]")
            people_counts = request.POST.getlist("blood_people_count[]")
            staff_counts = request.POST.getlist("blood_staff_count[]")

            for index in range(len(dates)):
                if not dates[index]:
                    continue

                BloodCollectionInfo.objects.create(
                    contract=contract,
                    collection_date=dates[index],
                    location=locations[index],
                    people_count=people_counts[index],
                    staff_count=staff_counts[index],
                )

            contract.distribute_slots()

    except ValidationError as exc:
        messages.error(request, f"Lỗi phân bổ: {exc}")
        return redirect("contract:contract_list")
    except Exception as exc:
        messages.error(request, f"Đã xảy ra lỗi: {exc}")
        return redirect("contract:contract_list")

    messages.success(request, "Đã tạo hợp đồng thành công ✅")
    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def delete_appointment(request, contract_id):
    contract = get_object_or_404(HealthContract, id=contract_id)

    if contract.is_approved:
        messages.warning(request, "Hợp đồng đã duyệt, không thể xóa.")
        return redirect("contract:contract_list")

    if request.user != contract.created_by and not request.user.groups.filter(name="Managers").exists():
        raise PermissionDenied("Bạn không có quyền xóa hợp đồng này.")

    try:
        with transaction.atomic():
            contract.schedules.all().delete()
            contract.delete()
            messages.success(request, "Hợp đồng đã được xóa.")
    except Exception as exc:
        messages.error(request, f"Lỗi khi xóa hợp đồng: {exc}")

    return redirect("contract:contract_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def approve_contract(request, contract_id):
    contract = get_object_or_404(HealthContract, id=contract_id)

    if not request.user.groups.filter(name="Managers").exists():
        raise PermissionDenied("Bạn không có quyền duyệt hợp đồng này.")

    contract.is_approved = True
    contract.save(update_fields=["is_approved", "updated_at"])

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "contract_updates",
        {
            "type": "send_contract_approved",
            "contract_id": contract.id,
        },
    )

    return JsonResponse({"success": True})


def normalize_str(value):
    return str(value).strip().lower()


# =========================
# Scheduling compatibility façade
# =========================

@login_required(login_url="authentication:staff_login")
def schedule_table(request):
    return scheduling_schedule_table(request)


@login_required(login_url="authentication:staff_login")
def redistribute_slots(request, contract_id):
    return scheduling_redistribute_slots(request, contract_id)


def register_schedule(request):
    return scheduling_register_schedule(request)


def submit_registration(request):
    return scheduling_submit_registration(request)


def show_thank_you(request):
    return scheduling_show_thank_you(request)