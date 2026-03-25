from apps.account.selectors.patient_profile_selectors import build_patient_profile_context


def get_patient_profile_payload(*, patient):
    """
    Transitional profile service.
    Hiện tại đọc từ DB nội bộ qua app patients.
    """
    return build_patient_profile_context(patient=patient)