from apps.clinical.models import DentalExamination, ToothNotation
from apps.organizations.selectors.company_selectors import list_companies_for_actor
import re as _re
import base64
import mimetypes
from pathlib import Path

from apps.his_integration.selectors import get_active_his_patient_by_id

SIGNATURE_DIR = Path(__file__).resolve().parents[1] / "data" / "signature"

DOCTOR_SIGNATURES = {
    "hoat.dt": {
        "files": ["bs_hoat.png", "bs_hoat.jpg", "bs_hoat.jpeg"],
        "display_name": "Bs. Đỗ Thị Hoạt",
    },
    "huynh.htb": {
        "files": ["white_paper.png", "white_paper.jpg", "white_paper.jpeg"],
        "display_name": "Bs. Hồ Thị Bạch Huỳnh",
    },
}


def _build_signature_data_url(file_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "image/png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _build_doctor_signature_context(actor):
    username = (getattr(actor, "username", "") or "").strip().lower()
    config = DOCTOR_SIGNATURES.get(username, {})

    signature_url = ""
    for filename in config.get("files", []):
        candidate = SIGNATURE_DIR / filename
        if candidate.exists() and candidate.is_file():
            signature_url = _build_signature_data_url(candidate)
            break

    first_name = (getattr(actor, "first_name", "") or "").strip()
    last_name = (getattr(actor, "last_name", "") or "").strip()
    full_name = f"{last_name} {first_name}".strip() or (actor.get_full_name() or "").strip()
    doctor_name = config.get("display_name") or (f"Bs. {full_name}" if full_name else "")

    return {
        "doctor_signature_url": signature_url,
        "doctor_display_name": doctor_name,
    }


def _notation_sort_key(item):
    raw = item.code.strip()
    has_sqrt = "√" in raw
    clean = raw.replace("√", "").strip()
    m = _re.match(r"^(\d+)(?:\.(\d+))?$", clean)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2)) if m.group(2) else 0
        sqrt_offset = -1 if has_sqrt else 0
        return (major, sqrt_offset, minor)
    return (999, 0, 0)


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

    signature_context = _build_doctor_signature_context(actor)

    return {
        "companies": companies,
        "notations": notations,
        "notation_map": notation_map,
        "note_columns": _split_note_columns(notations, num_columns=3),
        "tooth_upper": tooth_upper,
        "tooth_lower": tooth_lower,
        **signature_context,
    }


def _patient_info_from_exam(dental_exam):
    """
    Trả về dict thông tin hành chính bệnh nhân từ exam.
    Ưu tiên his_patient → snapshot → patient legacy.
    """
    if dental_exam.his_patient_id:
        his_p = dental_exam.his_patient
        return {
            "patient_id": his_p.id,
            "full_name": his_p.full_name,
            "dob": his_p.birth_date_display,
            "gender": his_p.gioi_tinh,
            "patient_code": his_p.his_patient_code,
        }

    snapshot = dental_exam.patient_snapshot or {}
    p = dental_exam.patient
    return {
        "patient_id": p.id if p else None,
        "full_name": snapshot.get("ho_ten") or (p.ho_ten if p else ""),
        "dob": snapshot.get("ngay_sinh") or (
            p.ngay_sinh.strftime("%d/%m/%Y") if p and p.ngay_sinh else ""
        ),
        "gender": snapshot.get("gioi_tinh") or (p.gioi_tinh if p else ""),
        "patient_code": snapshot.get("ma_bn") or (p.ma_bn if p else ""),
    }


def build_dental_result_payload(*, patient_id=None, exam_id=None):
    """
    Trả về dữ liệu để prefill form.
    - exam_id: load bản ghi cụ thể
    - patient_id: HisPatientSync.id — load bản ghi mới nhất của BN HIS đó
    """
    if exam_id:
        dental_exam = DentalExamination.objects.select_related(
            "his_patient", "patient"
        ).get(id=exam_id)
        info = _patient_info_from_exam(dental_exam)

    elif patient_id:
        his_p = get_active_his_patient_by_id(patient_id=patient_id)
        if not his_p:
            raise ValueError("Không tìm thấy bệnh nhân HIS trong hệ thống.")

        dental_exam = (
            DentalExamination.objects.filter(his_patient=his_p)
            .order_by("-updated_at", "-id")
            .first()
        )
        info = {
            "patient_id": his_p.id,
            "full_name": his_p.full_name,
            "dob": his_p.birth_date_display,
            "gender": his_p.gioi_tinh,
            "patient_code": his_p.his_patient_code,
        }

    else:
        raise ValueError("Cần cung cấp exam_id hoặc patient_id.")

    data = {
        **info,
        "dental_exam_id": dental_exam.id if dental_exam else "",
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
        "exam_date": (
            dental_exam.created_at.strftime("%Y-%m-%d")
            if dental_exam and dental_exam.created_at
            else ""
        ),
        "created_at_value": (
            dental_exam.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if dental_exam and dental_exam.created_at
            else ""
        ),
        "latest_saved_at": (
            dental_exam.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            if dental_exam and dental_exam.updated_at
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
    Trả về danh sách lịch sử khám của bệnh nhân HIS, mới nhất trước.
    patient_id = HisPatientSync.id
    """
    his_patient = get_active_his_patient_by_id(patient_id=patient_id)
    if not his_patient:
        raise ValueError("Không tìm thấy bệnh nhân HIS trong hệ thống.")

    exams = (
        DentalExamination.objects.filter(his_patient=his_patient)
        .order_by("-created_at", "-id")
        .only(
            "id", "created_at", "conclusion", "health_classification",
            "tooth_loss_classification", "chewing_ability", "patient_snapshot",
        )[:30]
    )

    result = []
    for exam in exams:
        result.append({
            "id": exam.id,
            "created_at_display": (
                exam.created_at.strftime("%d/%m/%Y %H:%M") if exam.created_at else ""
            ),
            "exam_date": (
                exam.created_at.strftime("%Y-%m-%d") if exam.created_at else ""
            ),
            "patient_name": his_patient.full_name,
            "patient_code": his_patient.his_patient_code,
            "health_classification": exam.health_classification or "",
            "tooth_loss_classification": exam.tooth_loss_classification or "",
            "chewing_ability": str(exam.chewing_ability) if exam.chewing_ability is not None else "",
            "conclusion": exam.conclusion or "",
        })

    return result
