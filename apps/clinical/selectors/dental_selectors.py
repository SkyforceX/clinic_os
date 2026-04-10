from apps.clinical.models import DentalExamination, ToothNotation
from apps.organizations.selectors.company_selectors import list_companies_for_actor
from apps.patients.models import Patient
import re as _re


def _notation_sort_key(item):
    """
    Sort ký hiệu răng theo thứ tự số thực:
    0 → √1 → 1 → 2 → 3 → 3.1 → ... → 10 → 11 → 11.1 → 11.2 ...
    √X được xếp ngay trước X (√1 trước 1).
    """
    raw = item.code.strip()
    has_sqrt = "√" in raw
    clean = raw.replace("√", "").strip()
    m = _re.match(r"^(\d+)(?:\.(\d+))?$", clean)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2)) if m.group(2) else 0
        sqrt_offset = -1 if has_sqrt else 0   # √X ngay trước X
        return (major, sqrt_offset, minor)
    return (999, 0, 0)  # fallback cho code không phải số


def _split_note_columns(notations, num_columns=3):
    notations = list(notations)
    if not notations:
        return [[] for _ in range(num_columns)]
    size = (len(notations) + num_columns - 1) // num_columns
    return [notations[i : i + size] for i in range(0, len(notations), size)]


def build_dental_exam_page_context(*, actor):
    companies = list_companies_for_actor(actor)
    notations = sorted(ToothNotation.objects.all(), key=_notation_sort_key)
    notation_map = {item.code: item.description_vi for item in notations}

    tooth_upper = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
    tooth_lower = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]

    return {
        "companies": companies,
        "notations": notations,
        "notation_map": notation_map,
        "note_columns": _split_note_columns(notations, num_columns=3),
        "tooth_upper": tooth_upper,
        "tooth_lower": tooth_lower,
    }


def build_dental_result_payload(*, patient_id=None, exam_id=None):
    """
    Trả về dữ liệu để prefill form.
    Ưu tiên exam_id (load bản ghi cụ thể), fallback sang patient_id (load bản ghi mới nhất).
    """
    if exam_id:
        dental_exam = DentalExamination.objects.select_related("patient").get(id=exam_id)
        patient = dental_exam.patient
    elif patient_id:
        patient = Patient.objects.select_related("company").get(id=patient_id)
        dental_exam = (
            DentalExamination.objects.filter(patient=patient)
            .order_by("-created_at", "-id")
            .first()
        )
    else:
        raise ValueError("Cần cung cấp exam_id hoặc patient_id.")

    # Ưu tiên snapshot nếu có, fallback sang patient model
    snapshot = dental_exam.patient_snapshot if dental_exam and dental_exam.patient_snapshot else {}

    data = {
        "patient_id": patient.id,
        "dental_exam_id": dental_exam.id if dental_exam else "",
        "full_name": snapshot.get("ho_ten") or patient.ho_ten,
        "dob": snapshot.get("ngay_sinh") or (
            patient.ngay_sinh.strftime("%d/%m/%Y") if patient.ngay_sinh else ""
        ),
        "gender": snapshot.get("gioi_tinh") or patient.gioi_tinh,
        "patient_code": snapshot.get("ma_bn") or patient.ma_bn,
        "additional_notes": dental_exam.additional_notes if dental_exam else "",
        "loss_classification": dental_exam.tooth_loss_classification if dental_exam else "",
        "other_oral_conditions": dental_exam.other_oral_conditions if dental_exam else "",
        "chewing_ability": (
            str(dental_exam.chewing_ability)
            if dental_exam and dental_exam.chewing_ability is not None
            else ""
        ),
        "health_classification": dental_exam.health_classification if dental_exam else "",
        "conclusion": dental_exam.conclusion if dental_exam else "",
        # Ngày khám dùng để prefill printDate khi xem lịch sử
        "exam_date": (
            dental_exam.created_at.strftime("%Y-%m-%d")
            if dental_exam and dental_exam.created_at
            else ""
        ),
        "tooth_details": {},
    }

    if dental_exam and dental_exam.tooth_data:
        for tooth, notation_code in dental_exam.tooth_data.items():
            try:
                tooth_num = int(tooth)
            except (TypeError, ValueError):
                continue
            prefix = "tooth_upper" if 11 <= tooth_num <= 28 else "tooth_lower"
            data["tooth_details"][f"{prefix}_{tooth}"] = notation_code

    return data


def get_exam_history_for_patient(*, patient_id):
    """
    Trả về danh sách lịch sử khám của bệnh nhân, mới nhất trước.
    """
    patient = Patient.objects.get(id=patient_id)
    exams = (
        DentalExamination.objects.filter(patient=patient)
        .order_by("-created_at", "-id")
        .only(
            "id", "created_at", "conclusion", "health_classification",
            "tooth_loss_classification", "chewing_ability", "patient_snapshot",
        )[:30]
    )

    result = []
    for exam in exams:
        snapshot = exam.patient_snapshot or {}
        result.append({
            "id": exam.id,
            "created_at_display": (
                exam.created_at.strftime("%d/%m/%Y %H:%M") if exam.created_at else ""
            ),
            "exam_date": (
                exam.created_at.strftime("%Y-%m-%d") if exam.created_at else ""
            ),
            "patient_name": snapshot.get("ho_ten") or patient.ho_ten,
            "patient_code": snapshot.get("ma_bn") or patient.ma_bn,
            "health_classification": exam.health_classification or "",
            "tooth_loss_classification": exam.tooth_loss_classification or "",
            "chewing_ability": str(exam.chewing_ability) if exam.chewing_ability is not None else "",
            "conclusion": exam.conclusion or "",
        })

    return result
