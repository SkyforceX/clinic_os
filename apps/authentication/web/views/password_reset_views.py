from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.authentication.services.password_reset import (
    PasswordResetError,
    create_password_reset_otp,
    mark_otp_verified,
    reset_patient_password,
    validate_latest_otp,
)

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
    normalized_phone = normalize_phone(phone)

    patient = find_patient_for_reset(
        patient_code=patient_code,
        phone=normalized_phone,
    )
    if not patient:
        raise PasswordResetError("Có lỗi, không tìm thấy tài khoản")

    patient.password = make_password(new_password)
    patient.save(update_fields=["password"])
    return patient


def request_password_reset(request):
    if request.method == "POST":
        patient_code = request.POST.get("patient_code")
        phone = request.POST.get("phone")

        try:
            result = create_password_reset_otp(
                patient_code=patient_code,
                phone=phone,
            )

            request.session["reset_patient_code"] = patient_code
            request.session["reset_phone"] = result["phone"]

            messages.success(request, "OTP đã được gửi qua Zalo.")
            return redirect("authentication:verify_otp")

        except PasswordResetError as exc:
            messages.error(request, str(exc))

    return render(request, "authentication/forgot_password.html")


def verify_otp(request):
    if request.method == "POST":
        otp = request.POST.get("otp")
        phone = request.session.get("reset_phone")

        otp_request = validate_latest_otp(phone=phone, otp=otp)
        if not otp_request:
            messages.error(request, "OTP không đúng hoặc đã hết hạn.")
            return redirect("authentication:verify_otp")

        mark_otp_verified(otp_request=otp_request)
        request.session["otp_verified"] = True

        return redirect("authentication:reset_password")

    return render(request, "authentication/verify_otp.html")


def reset_password(request):
    if not request.session.get("otp_verified"):
        return redirect("authentication:forgot_password")

    if request.method == "POST":
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if new_password != confirm_password:
            messages.error(request, "Mật khẩu không khớp.")
            return redirect("authentication:reset_password")

        try:
            reset_patient_password(
                patient_code=request.session.get("reset_patient_code"),
                phone=request.session.get("reset_phone"),
                new_password=new_password,
            )

            request.session.flush()
            messages.success(request, "Đặt lại mật khẩu thành công.")
            return redirect("authentication:patient_login")

        except PasswordResetError as exc:
            messages.error(request, str(exc))

    return render(request, "authentication/reset_password.html")