from apps.patients.models import Patient


def get_current_patient_from_session(request):
    patient_id = request.session.get("patient_id")
    if not patient_id:
        return None

    return (
        Patient.objects.select_related("company")
        .filter(id=patient_id)
        .first()
    )