from apps.account.selectors.patient_profile_selectors import build_patient_profile_context


def get_patient_profile_payload(*, patient):
    """
    Transitional profile service.
    Hiện tại đọc từ patient object đang lưu trong session HIS.
    """
    return build_patient_profile_context(patient=patient)
