from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.clinical.models import DentalExamination
from apps.organizations.models import Company
from apps.patients.models import Patient
from apps.patients.services.patient_commands import (
    PatientValidationError,
    get_or_create_walkin_patient,
)


def _normalize_decimal(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


@transaction.atomic
def save_dental_examination(*, patient_id=None, payload):
    """
    Luôn tạo bản ghi mới (không upsert) để giữ lịch sử khám đầy đủ.
    - patient_id có giá trị  → bệnh nhân đã tồn tại (chọn từ danh sách)
    - patient_id là None     → khách lẻ, tìm/tạo Patient từ thông tin form
    Lưu kèm snapshot thông tin hành chính tại thời điểm khám.
    """
    if patient_id:
        patient = Patient.objects.select_related("company").get(id=int(patient_id))
    else:
        # Khách lẻ: tìm hoặc tạo mới patient từ dữ liệu form
        patient = get_or_create_walkin_patient(payload=payload)

    # company có thể là None (khách lẻ)
    company = patient.company
    if company is None and payload.get("company_id"):
        company = Company.objects.filter(id=payload.get("company_id")).first()

    # Snapshot thông tin hành chính tại thời điểm lưu
    patient_snapshot = {
        "ho_ten": patient.ho_ten,
        "ngay_sinh": patient.ngay_sinh.strftime("%d/%m/%Y") if patient.ngay_sinh else "",
        "gioi_tinh": patient.gioi_tinh,
        "ma_bn": patient.ma_bn,
    }

    now = timezone.now()

    exam = DentalExamination.objects.create(
        patient=patient,
        company=company,                          # None nếu khách lẻ
        patient_snapshot=patient_snapshot,
        additional_notes=payload.get("additional_notes", ""),
        tooth_data=payload.get("tooth_data") or {},
        tooth_loss_classification=payload.get("tooth_loss_classification", ""),
        other_oral_conditions=payload.get("other_oral_conditions", ""),
        chewing_ability=_normalize_decimal(payload.get("chewing_ability")),
        health_classification=payload.get("health_classification", ""),
        conclusion=payload.get("conclusion", ""),
        created_at=now,
        updated_at=now,
    )

    return exam
