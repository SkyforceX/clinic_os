from django.contrib import messages
from django.shortcuts import redirect, render

from apps.account.forms import ChangePasswordForm
from apps.account.policies import AccountPolicy
from apps.account.selectors.session_selectors import get_patient_from_session
from apps.account.services.password_change import (
    PasswordChangeError,
    change_patient_password,
)
from apps.account.services.patient_profile import get_patient_profile_payload
from apps.authentication.utils import patient_access_required


@patient_access_required
def patient_profile(request):
    patient = get_patient_from_session(request)
    if not patient:
        messages.error(request, "Bạn cần đăng nhập để xem hồ sơ.")
        return redirect("authentication:patient_login")

    if not AccountPolicy.can_view_self_profile(request, patient):
        messages.error(request, "Bạn không có quyền xem hồ sơ này.")
        return redirect("authentication:patient_login")

    request.session["patient_id"] = patient.id
    request.session["patient_code"] = patient.ma_bn
    request.session["patient_name"] = patient.ho_ten
    request.session["is_patient"] = True

    context = {
        "patient": get_patient_profile_payload(patient=patient),
        "error": None,
    }
    return render(request, "account/profile.html", context)


@patient_access_required
def change_password(request):
    patient = get_patient_from_session(request)
    if not patient:
        messages.error(request, "Bạn cần đăng nhập để đổi mật khẩu.")
        return redirect("authentication:patient_login")

    if not AccountPolicy.can_change_self_password(request, patient):
        messages.error(request, "Bạn không có quyền đổi mật khẩu cho tài khoản này.")
        return redirect("authentication:patient_login")

    form = ChangePasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            change_patient_password(
                patient=patient,
                current_password=form.cleaned_data["current_password"],
                new_password=form.cleaned_data["new_password"],
            )
            messages.success(request, "Đổi mật khẩu thành công.")
            return redirect("account:patient_profile")
        except PasswordChangeError as exc:
            form.add_error("current_password", str(exc))

    return render(
        request,
        "account/change_password.html",
        {
            "patient": patient,
            "form": form,
        },
    )