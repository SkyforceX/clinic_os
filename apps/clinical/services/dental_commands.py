from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.clinical.models import DentalExamination
from apps.his_integration.selectors import get_active_his_patient_by_id
from apps.organizations.models import Company


def _normalize_decimal(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


@transaction.atomic
def save_dental_examination(*, his_patient_id=None, patient_id=None, payload):
    """
    Luôn tạo bản ghi mới để giữ lịch sử khám đầy đủ.
    - his_patient_id: HisPatientSync.id
    - patient_id: giữ tham số để tương thích chữ ký cũ, không dùng local Patient nữa
    - không có HIS id: lưu snapshot khách lẻ trực tiếp, không tạo patients.Patient
    """
    his_patient = None
    patient = None
    company = None

    if his_patient_id:
        his_patient = get_active_his_patient_by_id(patient_id=int(his_patient_id))
        if not his_patient:
            raise ValueError("Không tìm thấy bệnh nhân HIS trong hệ thống.")

        patient_snapshot = {
            "ho_ten": his_patient.full_name,
            "ngay_sinh": his_patient.birth_date_display,
            "gioi_tinh": his_patient.gioi_tinh,
            "ma_bn": his_patient.his_patient_code,
        }
        if payload.get("company_id"):
            company = Company.objects.filter(id=payload.get("company_id")).first()

    else:
        patient_snapshot = {
            "ho_ten": payload.get("full_name", ""),
            "ngay_sinh": payload.get("dob", ""),
            "gioi_tinh": payload.get("gender", ""),
            "ma_bn": payload.get("patient_code", ""),
        }
        if payload.get("company_id"):
            company = Company.objects.filter(id=payload.get("company_id")).first()

    now = timezone.now()

    exam = DentalExamination.objects.create(
        patient=patient,
        his_patient=his_patient,
        company=company,
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
