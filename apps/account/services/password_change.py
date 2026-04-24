from django.contrib.auth.hashers import make_password

from apps.authentication.services.patient_auth import _verify_patient_password


class PasswordChangeError(Exception):
    pass


def change_patient_password(*, patient, current_password, new_password):
    if not patient:
        raise PasswordChangeError("Không tìm thấy tài khoản bệnh nhân.")

    current_password = str(current_password or "").strip()
    new_password = str(new_password or "").strip()

    if not current_password:
        raise PasswordChangeError("Vui lòng nhập mật khẩu hiện tại.")

    if len(new_password) < 6:
        raise PasswordChangeError("Mật khẩu mới phải có ít nhất 6 ký tự.")

    if not _verify_patient_password(patient, current_password):
        raise PasswordChangeError("Mật khẩu hiện tại không đúng.")

    if hasattr(patient, "password_raw"):
        patient.password_raw = make_password(new_password)
        patient.save(update_fields=["password_raw"])
        return patient

    patient.password = make_password(new_password)
    patient.save(update_fields=["password"])
    return patient
