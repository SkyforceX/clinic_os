import json
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.authentication.selectors.session_selectors import get_current_patient_from_session
from apps.authentication.utils import patient_access_required
from apps.booking.models import HisAppointmentPushLog
from apps.booking.tasks import push_appointment_to_his_task
from apps.scheduling.models import ScheduleSlot
from apps.scheduling.selectors.schedule_selectors import (
    build_patient_registration_calendar,
    get_existing_appointment_for_patient_in_schedule_config,
    get_existing_appointment_for_patient_in_slot,
    get_latest_contract_for_patient,
    get_latest_schedule_config_for_patient,
)
from apps.scheduling.services.appointment_commands import (
    RegistrationCommand,
    SchedulingRegistrationError,
    register_or_move_patient_appointment,
)

logger = logging.getLogger(__name__)


def _dispatch_his_push_for_appointment(*, appointment):
    push_log = HisAppointmentPushLog.objects.create(
        appointment=appointment,
        status=HisAppointmentPushLog.PushStatus.QUEUED,
    )

    try:
        push_appointment_to_his_task.delay(appointment.id, log_id=push_log.id)
        return
    except Exception:
        logger.exception(
            "Failed to dispatch Celery HIS push for appointment_id=%s. Falling back to direct push.",
            getattr(appointment, "id", None),
        )

    from apps.booking.services import push_appointment_to_his

    try:
        result = push_appointment_to_his(appointment)
    except Exception as exc:
        HisAppointmentPushLog.objects.filter(pk=push_log.id).update(
            status=HisAppointmentPushLog.PushStatus.FAILED,
            attempt=1,
            error=str(exc),
            pushed_at=timezone.now(),
        )
        logger.exception(
            "Direct fallback HIS push failed for appointment_id=%s.",
            getattr(appointment, "id", None),
        )
        return

    if result.skipped_reason:
        final_status = HisAppointmentPushLog.PushStatus.SKIPPED
    elif result.success:
        final_status = HisAppointmentPushLog.PushStatus.SUCCESS
    else:
        final_status = HisAppointmentPushLog.PushStatus.FAILED

    HisAppointmentPushLog.objects.filter(pk=push_log.id).update(
        status=final_status,
        attempt=1,
        endpoint=result.endpoint or "",
        payload=result.payload,
        http_status_code=result.status_code,
        response_data=result.response_data,
        response_text=(result.response_text or "")[:4000],
        error=result.error or "",
        skipped_reason=result.skipped_reason or "",
        pushed_at=timezone.now(),
    )


@patient_access_required
def register_schedule(request):
    """
    Trang đặt lịch khám của bệnh nhân doanh nghiệp.

    Yêu cầu: bệnh nhân đã đăng nhập qua patient session,
    và công ty của bệnh nhân có hợp đồng đang còn hiệu lực.
    """
    patient = getattr(request, "current_patient", None) or get_current_patient_from_session(request)
    if not patient:
        return redirect("authentication:patient_login")

    schedule_config = get_latest_schedule_config_for_patient(patient)
    contract = get_latest_contract_for_patient(patient)
    if not schedule_config:
        messages.error(
            request,
            "Bạn chưa thể đăng ký lịch khám<br>Hãy liên hệ Phòng khám để được hướng dẫn.",
        )
        return redirect("authentication:patient_dashboard")

    actual_contract = getattr(getattr(schedule_config, "contract", None), "contract", None)
    effective_contract = actual_contract or contract
    calendar_payload = build_patient_registration_calendar(schedule_config=schedule_config)
    current_appointment = get_existing_appointment_for_patient_in_schedule_config(
        patient=patient,
        schedule_config=schedule_config,
    )
    his_package = getattr(schedule_config, "his_package", None)
    company_name = (
        getattr(his_package, "company_name", "")
        or (
            getattr(getattr(schedule_config, "quotation", None), "company", None)
            and schedule_config.quotation.company.name
        )
        or getattr(getattr(schedule_config, "quotation", None), "company_name", "")
        or (effective_contract.company.name if effective_contract else "")
    )

    context = {
        "months_data":      calendar_payload["months_data"],
        "today":            timezone.localdate(),
        "patient":          patient,
        "contract_id":      effective_contract.id if effective_contract else "",
        "schedule_config_id": schedule_config.id,
        "company_name":     company_name,
        "contract_start":   schedule_config.exam_start_date,
        "contract_end":     schedule_config.exam_end_date,
        "has_registered":   current_appointment is not None,
        "current_schedule": current_appointment.schedule_slot if current_appointment else None,
        "slot_status_json": json.dumps(calendar_payload["slot_status"]),
        "title_page":       "Đặt lịch khám sức khỏe",
        "request":          request,
    }
    return render(request, "booking/register_schedule.html", context)


@patient_access_required
def submit_registration(request):
    """
    Xử lý POST đăng ký / thay đổi ca khám.

    Form gửi lên: contract_id, date (YYYY-MM-DD), slot (AM/PM).
    Service `register_or_move_patient_appointment` xử lý toàn bộ logic
    kiểm tra slot, cập nhật counter, tạo/cập nhật Appointment.
    """
    if request.method != "POST":
        return redirect("booking:register_schedule")

    patient = getattr(request, "current_patient", None) or get_current_patient_from_session(request)
    if not patient:
        messages.warning(request, "Vui lòng đăng nhập để tiếp tục.")
        return redirect("authentication:patient_login")

    try:
        result = register_or_move_patient_appointment(
            RegistrationCommand(
                patient=patient,
                contract_id=request.POST.get("contract_id"),
                schedule_config_id=request.POST.get("schedule_config_id"),
                date_value=request.POST.get("date"),
                shift_value=request.POST.get("slot"),
            )
        )

        if result["is_same_slot"]:
            messages.info(request, "Bạn đã đăng ký ca này trước đó.")
            return redirect("booking:register_schedule")

        # Tạo log entry QUEUED, dispatch Celery task — không block request
        _dispatch_his_push_for_appointment(appointment=result["appointment"])

        query_string = urlencode({
            "schedule_id": result["schedule"].id,
            "update":      "1" if result["is_update"] else "0",
        })
        return redirect(reverse("booking:show_thank_you") + f"?{query_string}")

    except SchedulingRegistrationError as exc:
        messages.warning(request, str(exc))
        return redirect("booking:register_schedule")

    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("booking:register_schedule")


@patient_access_required
def show_thank_you(request):
    """
    Trang xác nhận sau khi đăng ký / cập nhật lịch hẹn.

    Luồng 2 bước (POST-Redirect-GET pattern):
    1. GET ?schedule_id=X  → lưu context vào session rồi redirect (tránh F5 re-submit)
    2. GET (không có params) → đọc session, render trang cảm ơn
    """
    if "schedule_id" in request.GET:
        schedule_id = request.GET.get("schedule_id")
        is_update   = request.GET.get("update") == "1"

        patient = getattr(request, "current_patient", None) or get_current_patient_from_session(request)
        if not patient:
            messages.error(request, "Bạn cần đăng nhập để xem thông tin.")
            next_url = (
                f"{reverse('booking:show_thank_you')}"
                f"?schedule_id={schedule_id}&update={'1' if is_update else '0'}"
            )
            return redirect(f"{reverse('authentication:patient_login')}?next={next_url}")

        schedule = get_object_or_404(ScheduleSlot, id=schedule_id)
        request.session["thankyou_ctx"] = {
            "schedule_id": schedule.id,
            "is_update":   is_update,
        }
        return redirect("booking:show_thank_you")

    # --- bước 2: render ---
    ctx = request.session.pop("thankyou_ctx", None)
    if not ctx:
        messages.info(request, "Vui lòng hoàn tất đặt lịch trước.")
        return redirect("booking:register_schedule")

    patient = getattr(request, "current_patient", None) or get_current_patient_from_session(request)
    if not patient:
        messages.error(request, "Bạn cần đăng nhập để xem thông tin.")
        return redirect("authentication:patient_login")

    schedule = get_object_or_404(ScheduleSlot, id=ctx["schedule_id"])

    appointment = get_existing_appointment_for_patient_in_slot(
        patient=patient,
        schedule_slot=schedule,
    )
    if not appointment:
        messages.error(request, "Bạn không có quyền xem lịch hẹn này.")
        return redirect("booking:register_schedule")

    return render(
        request,
        "booking/show_thank_you.html",
        {
            "schedule":   schedule,
            "patient":    patient,
            "is_update":  ctx.get("is_update", False),
            "title_page": "Đăng ký thành công",
        },
    )
