"""
apps/record_completion/services/completion_service.py
"""

from django.db import transaction

from apps.record_completion.models import (
    LOG_ACTION_ADVANCE,
    LOG_ACTION_RETURN,
    TOTAL_STEPS,
    RecordCompletion,
    RecordCompletionLog,
)
from apps.record_completion.policies import RecordCompletionPolicy


class AdvanceStepError(Exception):
    pass


class ReturnStepError(Exception):
    pass


@transaction.atomic
def advance_step(
    record: RecordCompletion,
    actor,
    note: str = "",
    ma_bn_scan: str = "",
) -> RecordCompletion:
    """
    Xác nhận bước current_step, chuyển sang bước tiếp theo.
    Raises AdvanceStepError nếu không hợp lệ.
    """
    if record.is_completed:
        raise AdvanceStepError("Hồ sơ này đã hoàn tất.")

    step = record.current_step
    if step >= TOTAL_STEPS:
        raise AdvanceStepError("Hồ sơ đã ở trạng thái hoàn tất.")

    if not RecordCompletionPolicy.can_advance_step(actor, step):
        raise AdvanceStepError(
            f"Bạn không có quyền xác nhận bước {step + 1} của hồ sơ này."
        )

    # Bước 5: bắt buộc quét / nhập đúng mã BN
    if step == 5:
        expected = record.checkin_record.snapshot_ma_bn.strip().upper()
        provided = (ma_bn_scan or "").strip().upper()
        if not provided:
            raise AdvanceStepError("Vui lòng nhập / quét mã bệnh nhân để xác nhận.")
        if provided != expected:
            raise AdvanceStepError("Mã bệnh nhân không khớp. Vui lòng kiểm tra lại.")

    # Bước 0: lưu note vào checklist_note
    if step == 0 and note:
        record.checklist_note = note

    RecordCompletionLog.objects.create(
        record_completion=record,
        step=step,
        action=LOG_ACTION_ADVANCE,
        actor=actor,
        note=note or "",
    )

    record.current_step = step + 1
    if record.current_step >= TOTAL_STEPS:
        record.is_completed = True

    record.save(update_fields=["current_step", "is_completed", "checklist_note", "updated_at"])
    return record


@transaction.atomic
def return_step(
    record: RecordCompletion,
    actor,
    note: str = "",
) -> RecordCompletion:
    """
    Trả hồ sơ về bước trước (current_step - 1).
    Lý do (note) là bắt buộc.
    Raises ReturnStepError nếu không hợp lệ.
    """
    if record.is_completed:
        raise ReturnStepError("Hồ sơ đã hoàn tất, không thể trả về bước trước.")

    step = record.current_step
    if step <= 0:
        raise ReturnStepError("Đây là bước đầu tiên, không thể trả về.")

    if not RecordCompletionPolicy.can_advance_step(actor, step):
        raise ReturnStepError(
            f"Bạn không có quyền trả về bước {step} của hồ sơ này."
        )

    if not note.strip():
        raise ReturnStepError("Vui lòng nhập lý do trả về để ghi nhận.")

    RecordCompletionLog.objects.create(
        record_completion=record,
        step=step,
        action=LOG_ACTION_RETURN,
        actor=actor,
        note=note.strip(),
    )

    record.current_step = step - 1
    record.save(update_fields=["current_step", "updated_at"])
    return record
