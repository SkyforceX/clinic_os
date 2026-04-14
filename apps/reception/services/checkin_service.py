"""
apps/reception/services/checkin_service.py
===========================================
Business logic cho check-in / check-out.
"""

from datetime import date, datetime, timezone

from django.contrib.auth import authenticate
from django.db import transaction

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
    from apps.patients.models import Patient
    from apps.scheduling.models import ContractScheduleConfig

    exam_date = exam_date or date.today()

    try:
        patient = Patient.objects.select_related("company").get(ma_bn=ma_bn.strip().upper())
    except Patient.DoesNotExist:
        return None, "Không tìm thấy mã bệnh nhân này trong hệ thống."

    # Tìm schedule config của công ty có khám ngày hôm nay
    schedule_config = None
    if patient.company_id:
        schedule_config = (
            ContractScheduleConfig.objects
            .filter(
                quotation__company_id=patient.company_id,
                exam_start_date__lte=exam_date,
                exam_end_date__gte=exam_date,
            )
            .select_related("quotation__company")
            .first()
        )
        if not schedule_config:
            # Thử qua contract
            schedule_config = (
                ContractScheduleConfig.objects
                .filter(
                    contract__contract__company_id=patient.company_id,
                    exam_start_date__lte=exam_date,
                    exam_end_date__gte=exam_date,
                )
                .select_related("contract__contract__company")
                .first()
            )

    # Kiểm tra đã check-in hôm nay chưa
    existing = CheckInRecord.objects.filter(
        snapshot_ma_bn=patient.ma_bn,
        exam_date=exam_date,
    ).order_by("-created_at").first()

    company_name = ""
    exam_start = None
    exam_end = None

    if patient.company:
        company_name = patient.company.name
    if schedule_config:
        exam_start = schedule_config.exam_start_date
        exam_end   = schedule_config.exam_end_date
        if not company_name:
            sc = schedule_config
            if hasattr(sc, "quotation") and sc.quotation and sc.quotation.company:
                company_name = sc.quotation.company.name

    return {
        "patient":         patient,
        "schedule_config": schedule_config,
        "company_name":    company_name,
        "exam_start":      exam_start,
        "exam_end":        exam_end,
        "existing_record": existing,
        "already_checked_in":  existing is not None and existing.status == CheckInStatus.CHECKED_IN,
        "already_checked_out": existing is not None and existing.status == CheckInStatus.CHECKED_OUT,
        "is_deferred":         existing is not None and existing.status == CheckInStatus.DEFERRED,
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
    company_name    = result["company_name"]

    if result["already_checked_in"]:
        return None, "Khách hàng này đã check-in rồi."

    now = datetime.now(tz=timezone.utc)
    record = CheckInRecord.objects.create(
        patient          = patient,
        schedule_config  = schedule_config,
        company          = patient.company,
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
def do_checkout(record_id: int, note: str, operator, exam_date: date = None):
    """Chuyển bản ghi check-in sang trạng thái đã check-out."""
    exam_date = exam_date or date.today()
    try:
        record = CheckInRecord.objects.get(pk=record_id, exam_date=exam_date)
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
def do_defer(record_id: int, note: str, operator, exam_date: date = None):
    """Đánh dấu khách hàng quay lại sau (chưa khám xong)."""
    exam_date = exam_date or date.today()
    try:
        record = CheckInRecord.objects.get(pk=record_id, exam_date=exam_date)
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
