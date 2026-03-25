from apps.patients.models import Patient


def get_patient_from_session(request):
    patient_id = request.session.get("patient_id")
    patient_code = request.session.get("patient_code")

    patient = None
    if patient_id:
        patient = (
            Patient.objects.select_related("company")
            .filter(id=patient_id)
            .first()
        )

    if not patient and patient_code:
        patient = (
            Patient.objects.select_related("company")
            .filter(ma_bn__iexact=str(patient_code).strip())
            .first()
        )

    return patient