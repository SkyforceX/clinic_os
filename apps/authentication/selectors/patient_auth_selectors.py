from apps.patients.models import Patient


def find_patient_for_login(*, patient_code):
    return (
        Patient.objects.select_related("company")
        .filter(ma_bn__iexact=str(patient_code or "").strip())
        .first()
    )


def find_patient_for_reset(*, patient_code, phone):
    normalized_code = str(patient_code or "").strip()
    normalized_phone = str(phone or "").strip()
    return (
        Patient.objects.select_related("company")
        .filter(
            ma_bn__iexact=normalized_code,
            phone=normalized_phone,
        )
        .first()
    )