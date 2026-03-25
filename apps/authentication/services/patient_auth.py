from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password, identify_hasher

from apps.authentication.selectors.patient_auth_selectors import find_patient_for_login


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

    if isinstance(ngay_sinh, (date, datetime)):
        return ngay_sinh.strftime("%d%m%Y")

    if isinstance(ngay_sinh, str):
        raw = ngay_sinh.strip()
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
    stored_password = str(getattr(patient, "password", "") or "").strip()

    if stored_password:
        try:
            identify_hasher(stored_password)
            return check_password(password, stored_password)
        except Exception:
            return password == stored_password

    expected = _expected_password_from_dob(getattr(patient, "ngay_sinh", None))
    return password == expected


def authenticate_patient_credentials(*, patient_code, password):
    patient = find_patient_for_login(patient_code=patient_code)
    if not patient:
        raise PatientAuthenticationError("Mã BN không tồn tại.")

    raw_password = str(password or "").strip()
    if not _verify_patient_password(patient, raw_password):
        raise PatientAuthenticationError(
            "Mật khẩu không đúng (mặc định là ngày sinh định dạng ddmmyyyy)."
        )

    return patient


def login_patient_session(*, request, patient, success_message=True):
    logout(request)
    request.session.flush()
    request.session["patient_id"] = patient.id
    request.session["patient_code"] = patient.ma_bn
    request.session["patient_name"] = getattr(patient, "ho_ten", "")
    request.session["is_patient"] = True

    if success_message:
        messages.success(request, f"Chào mừng {patient.ho_ten}!")


def logout_patient_session(*, request):
    logout(request)
    request.session.flush()