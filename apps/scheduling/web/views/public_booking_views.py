import json
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.authentication.utils import patient_access_required
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, ScheduleSlot
from apps.scheduling.selectors.schedule_selectors import (
    build_patient_registration_calendar,
    get_existing_appointment_for_patient_in_contract,
    get_latest_contract_for_patient,
)
from apps.scheduling.services.appointment_commands import (
    RegistrationCommand,
    SchedulingRegistrationError,
    register_or_move_patient_appointment,
)


@patient_access_required
def register_schedule(request):
    patient_id = request.session.get("patient_id")
    if not patient_id:
        return redirect("authentication:patient_login")

    try:
        patient = Patient.objects.select_related("company").get(id=patient_id)
    except Patient.DoesNotExist:
        messages.error(request, "Không tìm thấy bệnh nhân.")
        return redirect("authentication:patient_dashboard")

    contract = get_latest_contract_for_patient(patient)
    if not contract:
        messages.error(
            request,
            "Bạn chưa thể đăng ký lịch khám<br>Hãy liên hệ Phòng khám để được hướng dẫn.",
        )
        return redirect("authentication:patient_dashboard")

    calendar_payload = build_patient_registration_calendar(contract=contract)
    current_appointment = get_existing_appointment_for_patient_in_contract(
        patient=patient,
        contract=contract,
    )

    context = {
        "months_data": calendar_payload["months_data"],
        "today": contract.start_date,
        "patient": patient,
        "contract_id": contract.id,
        "company_name": contract.company.name,
        "contract_start": contract.start_date,
        "contract_end": contract.end_date,
        "has_registered": current_appointment is not None,
        "current_schedule": current_appointment.schedule if current_appointment else None,
        "slot_status_json": json.dumps(calendar_payload["slot_status"]),
        "title_page": "Đặt lịch khám sức khỏe",
        "request": request,
    }
    return render(request, "booking/register_schedule.html", context)


@patient_access_required
def submit_registration(request):
    if request.method != "POST":
        return redirect("scheduling:register_schedule")

    patient_id = request.session.get("patient_id")
    if not patient_id:
        messages.warning(request, "Vui lòng đăng nhập để tiếp tục.")
        return redirect("authentication:patient_login")

    patient = get_object_or_404(Patient, id=patient_id)

    try:
        result = register_or_move_patient_appointment(
            RegistrationCommand(
                patient=patient,
                contract_id=request.POST.get("contract_id"),
                date_value=request.POST.get("date"),
                shift_value=request.POST.get("slot"),
            )
        )

        if result["is_same_slot"]:
            messages.info(request, "Bạn đã đăng ký ca này trước đó.")
            return redirect("scheduling:register_schedule")

        query_string = urlencode(
            {
                "schedule_id": result["schedule"].id,
                "update": "1" if result["is_update"] else "0",
            }
        )
        return redirect(reverse("scheduling:show_thank_you") + f"?{query_string}")

    except SchedulingRegistrationError as exc:
        messages.warning(request, str(exc))
        return redirect("scheduling:register_schedule")

    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("scheduling:register_schedule")


@patient_access_required
def show_thank_you(request):
    if "schedule_id" in request.GET:
        schedule_id = request.GET.get("schedule_id")
        is_update = request.GET.get("update") == "1"

        patient_id = request.session.get("patient_id")
        if not patient_id:
            messages.error(request, "Bạn cần đăng nhập để xem thông tin.")
            next_url = f"{reverse('scheduling:show_thank_you')}?schedule_id={schedule_id}&update={'1' if is_update else '0'}"
            return redirect(f"{reverse('authentication:patient_login')}?next={next_url}")

        schedule = get_object_or_404(ScheduleSlot, id=schedule_id)

        request.session["thankyou_ctx"] = {
            "schedule_id": schedule.id,
            "is_update": is_update,
        }
        return redirect("scheduling:show_thank_you")

    ctx = request.session.pop("thankyou_ctx", None)
    if not ctx:
        messages.info(request, "Vui lòng hoàn tất đặt lịch trước.")
        return redirect("scheduling:register_schedule")

    patient_id = request.session.get("patient_id")
    if not patient_id:
        messages.error(request, "Bạn cần đăng nhập để xem thông tin.")
        return redirect("authentication:patient_login")

    schedule = get_object_or_404(ScheduleSlot, id=ctx["schedule_id"])
    patient = get_object_or_404(Patient, id=patient_id)

    appointment = (
        Appointment.objects
        .filter(patient=patient, schedule=schedule)
        .first()
    )
    if not appointment:
        messages.error(request, "Bạn không có quyền xem lịch hẹn này.")
        return redirect("scheduling:register_schedule")

    return render(
        request,
        "booking/show_thank_you.html",
        {
            "schedule": schedule,
            "patient": patient,
            "is_update": ctx.get("is_update", False),
        },
    )