from apps.his_integration.selectors import get_active_his_patient_by_id


def get_current_patient_from_session(request):
    his_patient_sync_id = request.session.get("his_patient_sync_id")
    if not his_patient_sync_id:
        return None

    return get_active_his_patient_by_id(patient_id=his_patient_sync_id)
