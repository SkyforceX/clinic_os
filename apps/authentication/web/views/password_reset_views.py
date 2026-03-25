from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from apps.authentication.forms import ForgotPasswordForm, OtpVerifyForm, ResetPasswordForm
from apps.authentication.services.password_reset import (
    PasswordResetError,
    create_password_reset_otp,
    mark_otp_verified,
    reset_patient_password,
    validate_latest_otp,
)


@never_cache
def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            payload = create_password_reset_otp(
                patient_code=form.cleaned_data["patient_code"],
                phone=form.cleaned_data["phone"],
            )
            request.session["reset_patient_code"] = form.cleaned_data["patient_code"]
            request.session["reset_phone"] = payload["phone"]
            return redirect("authentication:verify_otp")
        except PasswordResetError as exc:
            form.add_error(None, str(exc))

    return render(request, "authentication/forgot_password.html", {"form": form})


def verify_otp(request):
    patient_code = request.session.get("reset_patient_code")
    phone = request.session.get("reset_phone")

    form = OtpVerifyForm(
        request.POST or None,
        initial={
            "patient_code": patient_code,
            "phone": phone,
        },
    )

    if request.method == "POST" and form.is_valid():
        otp_request = validate_latest_otp(
            phone=phone,
            otp=form.cleaned_data["otp"],
        )
        try:
            mark_otp_verified(otp_request=otp_request)
            request.session["otp_verified"] = True
            request.session["otp_value"] = form.cleaned_data["otp"]
            return redirect("authentication:reset_password")
        except PasswordResetError as exc:
            form.add_error("otp", str(exc))

    return render(request, "authentication/verify_otp.html", {"form": form})


@never_cache
def reset_password(request):
    patient_code = request.session.get("reset_patient_code")
    phone = request.session.get("reset_phone")
    otp_value = request.session.get("otp_value", "")

    if not request.session.get("otp_verified"):
        return redirect("authentication:forgot_password")

    form = ResetPasswordForm(
        request.POST or None,
        initial={
            "patient_code": patient_code,
            "phone": phone,
            "otp": otp_value,
        },
    )

    if request.method == "POST" and form.is_valid():
        try:
            reset_patient_password(
                patient_code=patient_code,
                phone=phone,
                new_password=form.cleaned_data["new_password"],
            )
            request.session.pop("reset_patient_code", None)
            request.session.pop("reset_phone", None)
            request.session.pop("otp_verified", None)
            request.session.pop("otp_value", None)

            messages.success(request, "Đổi mật khẩu thành công. Mời bạn đăng nhập lại.")
            return redirect("authentication:patient_login")
        except PasswordResetError as exc:
            form.add_error(None, str(exc))

    return render(request, "authentication/reset_password.html", {"form": form})