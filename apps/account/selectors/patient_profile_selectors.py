from apps.authentication.utils import _norm_gender


def build_patient_profile_context(*, patient):
    if not patient:
        return None

    return {
        "id": patient.id,
        "ma_bn": patient.ma_bn,
        "ho_ten": patient.ho_ten,
        "ngay_sinh": patient.ngay_sinh,
        "gioi_tinh": _norm_gender(getattr(patient, "gioi_tinh", "")),
        "phone": getattr(patient, "phone", None),
        "email": getattr(patient, "email", None),
        "dia_chi": getattr(patient, "dia_chi", None),
        "so_cmnd": getattr(patient, "so_cmnd", None),
        "company_name": getattr(getattr(patient, "company", None), "name", None),
    }