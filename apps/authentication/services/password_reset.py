from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.authentication.models import OtpRequest
from apps.authentication.otp_utils import generate_otp, send_zalo_otp
from apps.authentication.selectors.patient_auth_selectors import find_patient_for_reset
from apps.authentication.services.patient_auth import normalize_phone


class PasswordResetError(Exception):
    pass


def create_password_reset_otp(*, patient_code, phone):
    normalized_phone = normalize_phone(phone)
    patient = find_patient_for_reset(
        patient_code=patient_code,
        phone=normalized_phone,
    )
    if not patient:
        raise PasswordResetError("Không tìm thấy khách hàng hoặc số điện thoại không đúng")

    otp = generate_otp()
    send_zalo_otp(normalized_phone, otp)

    otp_request = OtpRequest.objects.create(
        phone=normalized_phone,
        otp=otp,
        time_sent=timezone.now(),
    )
    return {
        "patient": patient,
        "phone": normalized_phone,
        "otp_request": otp_request,
    }


def validate_latest_otp(*, phone, otp):
    return (
        OtpRequest.objects.filter(
            phone=str(phone or "").strip(),
            otp=str(otp or "").strip(),
            used=False,
        )
        .order_by("-time_sent")
        .first()
    )


def mark_otp_verified(*, otp_request):
    if not otp_request or not otp_request.is_valid():
        raise PasswordResetError("OTP không đúng hoặc đã hết hạn")

    otp_request.used = True
    otp_request.save(update_fields=["used"])


def reset_patient_password(*, patient_code, phone, new_password):
    patient = find_patient_for_reset(
        patient_code=patient_code,
        phone=phone,
    )
    if not patient:
        raise PasswordResetError("Có lỗi, không tìm thấy tài khoản")

    patient.password = make_password(new_password)
    patient.save(update_fields=["password"])
    return patient