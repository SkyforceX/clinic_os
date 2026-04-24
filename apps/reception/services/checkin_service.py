"""
apps/reception/services/checkin_service.py
===========================================
Business logic cho check-in / check-out.
"""

from datetime import date, datetime, timezone

from django.contrib.auth import authenticate
from django.db import transaction

from apps.his_integration.selectors import (
    find_his_patient_for_login,
    list_active_schedule_configs_for_his_patient,
)
from apps.reception.models import CheckInRecord, CheckInStatus
from apps.reception.policies import ReceptionPolicy


def authenticate_operator(username: str, password: str):
    """
    Xác thực thư ký y khoa để truy cập công cụ check-in.
    Trả về user nếu hợp lệ và có quyền, ngược lại None.
    """
    user = authenticate(username=username, password=password)
    if user is None:
        return None, "Sai tên đăng nhập hoặc mật khẩu."
    if not user.is_active:
        return None, "Tài khoản đã bị vô hiệu hóa."
    if not ReceptionPolicy.can_access_checkin_tool(user):
        return None, "Tài khoản không có quyền truy cập công cụ này."
    return user, None


def lookup_patient(ma_bn: str, exam_date: date = None):
    """
    Tra cứu bệnh nhân theo mã và tìm lịch khám phù hợp.

    Trả về dict hoặc None nếu không tìm thấy.
    """
    exam_date = exam_date or date.today()

    patient = find_his_patient_for_login(patient_code=ma_bn)
    if not patient:
        return None, "Không tìm thấy mã bệnh nhân này trong hệ thống."

    schedule_configs = list_active_schedule_configs_for_his_patient(
        patient_code=patient.his_patient_code,
    )
    schedule_config = (
        schedule_configs
        .filter(exam_start_date__lte=exam_date, exam_end_date__gte=exam_date)
        .first()
    ) or schedule_configs.first()

    # Kiểm tra đã từng check-in trong kỳ khám của hợp đồng chưa.
    # Scope tìm kiếm: toàn bộ kỳ [exam_start, exam_end] của schedule_config
    # (không chỉ hôm nay) — mỗi BN chỉ được check-in 1 lần/hợp đồng.
    existing = None
    if schedule_config:
        existing = (
            CheckInRecord.objects
            .filter(
                snapshot_ma_bn=patient.ma_bn,
                exam_date__range=[
                    schedule_config.exam_start_date,
                    schedule_config.exam_end_date,
                ],
            )
            .order_by("-exam_date", "-created_at")
            .first()
        )
    else:
        # Fallback: không có lịch khám — chỉ kiểm tra hôm nay
        existing = (
            CheckInRecord.objects
            .filter(
                snapshot_ma_bn=patient.ma_bn,
                exam_date=exam_date,
            )
            .order_by("-created_at")
            .first()
        )

    company_name = ""
    company = None
    exam_start = None
    exam_end = None

    if schedule_config:
        exam_start = schedule_config.exam_start_date
        exam_end   = schedule_config.exam_end_date
        his_package = getattr(schedule_config, "his_package", None)
        quotation = getattr(schedule_config, "quotation", None)
        contract_profile = getattr(schedule_config, "contract", None)
        contract = getattr(contract_profile, "contract", None) if contract_profile else None

        company = (
            getattr(his_package, "organization", None)
            or getattr(quotation, "company", None)
            or getattr(contract, "company", None)
        )
        company_name = (
            getattr(his_package, "company_name", "")
            or getattr(company, "name", "")
            or getattr(quotation, "company_name", "")
            or getattr(contract_profile, "company_name_snapshot", "")
        )

    return {
        "patient":         patient,
        "schedule_config": schedule_config,
        "company":         company,
        "company_name":    company_name,
        "exam_start":      exam_start,
        "exam_end":        exam_end,
        "existing_record": existing,
        "already_checked_in":  existing is not None and existing.status == CheckInStatus.CHECKED_IN,
        "already_checked_out": existing is not None and existing.status == CheckInStatus.CHECKED_OUT,
        "is_deferred":         existing is not None and existing.status == CheckInStatus.DEFERRED,
        # True nếu BN đã hoàn thành (checkout) trong kỳ hợp đồng — block mọi check-in mới
        "contract_done":       existing is not None and existing.status == CheckInStatus.CHECKED_OUT,
    }, None


@transaction.atomic
def do_checkin(ma_bn: str, note: str, operator, exam_date: date = None):
    """Tạo bản ghi check-in mới."""
    exam_date = exam_date or date.today()
    result, err = lookup_patient(ma_bn, exam_date)
    if err:
        return None, err

    patient         = result["patient"]
    schedule_config = result["schedule_config"]
    company         = result["company"]
    company_name    = result["company_name"]

    # Guard: không cho check-in nếu đã có record trong kỳ khám
    if result["already_checked_in"]:
        return None, "Khách hàng này đã check-in rồi."
    if result["already_checked_out"]:
        return None, "Khách hàng này đã hoàn thành khám rồi, không thể check-in lại."

    now = datetime.now(tz=timezone.utc)
    record = CheckInRecord.objects.create(
        patient          = None,
        his_patient_sync = patient,
        schedule_config  = schedule_config,
        company          = company,
        snapshot_ma_bn   = patient.ma_bn,
        snapshot_ho_ten  = patient.ho_ten,
        snapshot_gioi_tinh   = patient.gioi_tinh or "",
        snapshot_ngay_sinh   = patient.ngay_sinh,
        snapshot_company_name = company_name,
        snapshot_exam_start  = result["exam_start"],
        snapshot_exam_end    = result["exam_end"],
        exam_date      = exam_date,
        status         = CheckInStatus.CHECKED_IN,
        checked_in_at  = now,
        note           = note.strip(),
        operator       = operator,
    )
    return record, None


@transaction.atomic
def do_checkout(record_id: int, note: str, operator):
    """Chuyển bản ghi check-in sang trạng thái đã check-out.

    Không filter thêm exam_date — record_id đã đủ định danh duy nhất.
    Hỗ trợ trường hợp BN check-in ngày trước, checkout vào ngày sau trong kỳ.
    """
    try:
        record = CheckInRecord.objects.get(pk=record_id)
    except CheckInRecord.DoesNotExist:
        return None, "Không tìm thấy bản ghi check-in."

    if record.status == CheckInStatus.CHECKED_OUT:
        return None, "Khách hàng đã check-out rồi."

    now = datetime.now(tz=timezone.utc)
    record.status         = CheckInStatus.CHECKED_OUT
    record.checked_out_at = now
    if note.strip():
        record.note = (record.note + "\n" + note.strip()).strip()
    record.operator = operator
    record.save(update_fields=["status", "checked_out_at", "note", "operator", "updated_at"])
    return record, None


@transaction.atomic
def do_defer(record_id: int, note: str, operator):
    """Đánh dấu khách hàng quay lại sau (chưa khám xong).

    Không filter thêm exam_date — record_id đã đủ định danh duy nhất.
    """
    try:
        record = CheckInRecord.objects.get(pk=record_id)
    except CheckInRecord.DoesNotExist:
        return None, "Không tìm thấy bản ghi check-in."

    now = datetime.now(tz=timezone.utc)
    record.status      = CheckInStatus.DEFERRED
    record.deferred_at = now
    if note.strip():
        record.note = (record.note + "\n[Hoãn] " + note.strip()).strip()
    record.operator = operator
    record.save(update_fields=["status", "deferred_at", "note", "operator", "updated_at"])
    return record, None
