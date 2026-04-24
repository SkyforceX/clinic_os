from datetime import datetime

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password, identify_hasher

from apps.his_integration.selectors import (
    find_his_patient_for_login,
    get_latest_schedule_config_for_his_patient,
    verify_his_patient_birth_date,
)


class PatientAuthenticationError(Exception):
    pass


def normalize_phone(phone):
    value = str(phone or "").strip().replace(" ", "").replace("-", "")
    if value.startswith("0") and len(value) >= 10:
        return "84" + value[1:]
    if value.startswith("84") and len(value) > 10:
        return value
    return value


def _expected_password_from_dob(ngay_sinh):
    if not ngay_sinh:
        return ""

    if hasattr(ngay_sinh, "strftime"):
        return ngay_sinh.strftime("%d%m%Y")

    raw = str(ngay_sinh or "").strip()
    if not raw:
        return ""

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d%m%Y"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            return parsed.strftime("%d%m%Y")
        except ValueError:
            continue

    return ""


def _verify_patient_password(patient, password):
    stored_password = str(
        getattr(patient, "password_raw", None)
        or getattr(patient, "password", None)
        or ""
    ).strip()

    if stored_password:
        try:
            identify_hasher(stored_password)
            return check_password(password, stored_password)
        except Exception:
            return password == stored_password

    expected = _expected_password_from_dob(getattr(patient, "ngay_sinh", None))
    return str(password or "").strip() == expected


def authenticate_patient_credentials(*, patient_code, password):
    raw_password = str(password or "").strip()
    for fmt in ("%d%m%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            date_of_birth = datetime.strptime(raw_password, fmt).date()
            return authenticate_patient_by_his(
                patient_code=patient_code,
                date_of_birth=date_of_birth,
            )
        except ValueError:
            continue

    raise PatientAuthenticationError("Ngày sinh không đúng.")


def authenticate_patient_by_his(*, patient_code: str, date_of_birth):
    """
    Xác thực bệnh nhân qua dữ liệu đồng bộ từ HIS (mã BN + ngày sinh).
    Trả về HisPatientSync nếu hợp lệ, raise PatientAuthenticationError nếu không.
    """
    his_patient = find_his_patient_for_login(patient_code=patient_code)
    if not his_patient:
        raise PatientAuthenticationError("Mã BN không tìm thấy trong hệ thống.")

    if not verify_his_patient_birth_date(his_patient, date_of_birth):
        raise PatientAuthenticationError("Ngày sinh không đúng.")

    schedule_config = get_latest_schedule_config_for_his_patient(patient_code=patient_code)
    if not schedule_config:
        raise PatientAuthenticationError("Mã BN chưa được gán vào gói khám có lịch đăng ký.")

    return his_patient


def login_patient_session(*, request, patient, success_message=True):
    logout(request)
    request.session.flush()
    request.session["his_patient_sync_id"] = patient.id
    request.session["patient_code"] = patient.his_patient_code
    request.session["patient_name"] = getattr(patient, "full_name", "")
    request.session["is_patient"] = True

    if success_message:
        messages.success(request, f"Chào mừng {patient.full_name}!")


def logout_patient_session(*, request):
    logout(request)
    request.session.flush()
