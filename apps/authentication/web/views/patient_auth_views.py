from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.authentication.forms import PatientLoginForm
from apps.authentication.selectors.session_selectors import get_current_patient_from_session
from apps.authentication.services.patient_auth import (
    PatientAuthenticationError,
    authenticate_patient_by_his,
    login_patient_session,
    logout_patient_session,
)
from apps.authentication.utils import patient_access_required
from apps.scheduling.selectors.schedule_selectors import get_latest_schedule_config_for_patient


def patient_login(request):
    form = PatientLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        patient_code = form.cleaned_data["patient_code"]
        try:
            patient = authenticate_patient_by_his(
                patient_code=patient_code,
                date_of_birth=form.cleaned_data["date_of_birth"],
            )
            login_patient_session(request=request, patient=patient)

            if get_latest_schedule_config_for_patient(patient):
                return redirect("scheduling:register_schedule")
            return redirect("authentication:patient_dashboard")

        except PatientAuthenticationError as exc:
            message = str(exc)
            if "Mã BN" in message:
                form.add_error("patient_code", message)
            else:
                form.add_error("date_of_birth", message)

    return render(request, "authentication/login_form.html", {"form": form, "debug": settings.DEBUG})


@patient_access_required
def patient_dashboard(request):
    patient = getattr(request, "current_patient", None) or get_current_patient_from_session(request)
    if not patient:
        return redirect("authentication:patient_login")

    return render(
        request,
        "authentication/patient_dashboard.html",
        {
            "patient": patient,
        },
    )


def patient_logout(request):
    logout_patient_session(request=request)
    messages.info(request, "Bạn đã đăng xuất.")
    return redirect("authentication:patient_login")
