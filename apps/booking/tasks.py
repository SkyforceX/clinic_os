import logging
from datetime import timedelta

from background_task import background
from celery import shared_task
from django.utils import timezone

from apps.contract.models import Contract
from apps.contract.models.contract import ContractStatus

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="booking.push_appointment_to_his",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def push_appointment_to_his_task(self, appointment_id: int, log_id: int | None = None):
    """
    Async push lịch hẹn lên HIS AppService.

    - Tự retry tối đa 3 lần (sau 60s, 120s, 180s) nếu push thất bại.
    - Mọi kết quả được ghi vào HisAppointmentPushLog.
    """
    from apps.booking.models import Appointment, HisAppointmentPushLog
    from apps.booking.services import push_appointment_to_his

    PushStatus = HisAppointmentPushLog.PushStatus
    attempt_no = self.request.retries + 1

    appointment = (
        Appointment.objects
        .select_related(
            "patient",
            "his_patient_sync",
            "schedule_slot",
            "schedule_slot__contract__company",
            "schedule_slot__quotation__company",
        )
        .filter(pk=appointment_id)
        .first()
    )

    if not appointment:
        logger.warning("push_appointment_to_his_task: appointment_id=%s not found", appointment_id)
        if log_id:
            HisAppointmentPushLog.objects.filter(pk=log_id).update(
                status=PushStatus.FAILED,
                error=f"Appointment #{appointment_id} không tồn tại.",
                attempt=attempt_no,
                pushed_at=timezone.now(),
            )
        return

    try:
        result = push_appointment_to_his(appointment)
    except Exception as exc:
        logger.exception(
            "push_appointment_to_his_task: unexpected error appointment_id=%s attempt=%s",
            appointment_id, attempt_no,
        )
        if log_id:
            HisAppointmentPushLog.objects.filter(pk=log_id).update(
                status=PushStatus.FAILED,
                error=str(exc),
                attempt=attempt_no,
                pushed_at=timezone.now(),
            )
        raise self.retry(
            exc=exc,
            countdown=60 * attempt_no,
        )

    # Xác định trạng thái cuối
    if result.skipped_reason:
        final_status = PushStatus.SKIPPED
    elif result.success:
        final_status = PushStatus.SUCCESS
    else:
        final_status = PushStatus.FAILED

    log_fields = dict(
        status=final_status,
        attempt=attempt_no,
        endpoint=result.endpoint or "",
        payload=result.payload,
        http_status_code=result.status_code,
        response_data=result.response_data,
        response_text=(result.response_text or "")[:4000],
        error=result.error or "",
        skipped_reason=result.skipped_reason or "",
        pushed_at=timezone.now(),
    )

    if log_id:
        HisAppointmentPushLog.objects.filter(pk=log_id).update(**log_fields)
    else:
        HisAppointmentPushLog.objects.create(appointment=appointment, **log_fields)

    if final_status == PushStatus.FAILED:
        logger.warning(
            "push_appointment_to_his_task FAILED appointment_id=%s attempt=%s/%s error=%r",
            appointment_id, attempt_no, self.max_retries + 1, result.error,
        )
        raise self.retry(
            exc=Exception(result.error or "HIS push failed"),
            countdown=60 * attempt_no,
        )

    logger.info(
        "push_appointment_to_his_task %s appointment_id=%s attempt=%s",
        final_status, appointment_id, attempt_no,
    )


@background(schedule=60)
def auto_terminate_contracts():
    today = timezone.now().date()
    expired_date = today - timedelta(days=16)

    qs = Contract.objects.filter(
        status__in=[ContractStatus.SUBMITTED, ContractStatus.APPROVED, ContractStatus.ACTIVE],
        created_at__date__lte=expired_date,
    )

    updated = 0
    for contract in qs:
        contract.status = ContractStatus.TERMINATED
        contract.terminated_at = today
        contract.save(update_fields=["status", "terminated_at", "updated_at"])
        updated += 1

    print(f"Đã cập nhật {updated} hợp đồng hết hạn.")