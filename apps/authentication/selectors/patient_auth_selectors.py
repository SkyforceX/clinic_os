from apps.patients.models import Patient


def find_patient_for_login(*, patient_code):
    return (
        Patient.objects.select_related("company")
        .filter(ma_bn__iexact=str(patient_code or "").strip())
        .first()
    )


def _normalize_phone(value):
    raw = str(value or "").strip().replace(" ", "").replace("-", "")
    if raw.startswith("0") and len(raw) >= 10:
        return "84" + raw[1:]
    if raw.startswith("84") and len(raw) >= 10:
        return raw
    return raw


def find_patient_for_reset(*, patient_code, phone):
    normalized_code = str(patient_code or "").strip()
    normalized_phone = _normalize_phone(phone)

    patient = (
        Patient.objects.select_related("company")
        .filter(ma_bn__iexact=normalized_code)
        .first()
    )
    if not patient:
        return None

    patient_phone = _normalize_phone(getattr(patient, "phone", ""))
    if not patient_phone or patient_phone != normalized_phone:
        return None

    return patient