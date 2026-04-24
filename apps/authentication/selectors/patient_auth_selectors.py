from apps.his_integration.selectors import find_his_patient_for_login


def find_patient_for_login(*, patient_code):
    return find_his_patient_for_login(patient_code=patient_code)


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

    patient = find_his_patient_for_login(patient_code=normalized_code)
    if not patient:
        return None

    patient_phone = _normalize_phone(getattr(patient, "phone", ""))
    if not patient_phone or patient_phone != normalized_phone:
        return None

    return patient
