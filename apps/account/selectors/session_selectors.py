from apps.authentication.selectors.session_selectors import get_current_patient_from_session


def get_patient_from_session(request):
    return get_current_patient_from_session(request)
