from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.authentication.forms import PatientLoginForm
from apps.authentication.services.patient_auth import (
    PatientAuthenticationError,
    authenticate_patient_credentials,
    login_patient_session,
    logout_patient_session,
)
from apps.authentication.utils import patient_access_required
from apps.patients.models import Patient


def patient_login(request):
    form = PatientLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            patient = authenticate_patient_credentials(
                patient_code=form.cleaned_data["patient_code"],
                password=form.cleaned_data["password"],
            )
            login_patient_session(request=request, patient=patient)
            return redirect("booking:register_schedule")
        except PatientAuthenticationError as exc:
            message = str(exc)
            if "Mã BN" in message:
                form.add_error("patient_code", message)
            else:
                form.add_error("password", message)

    return render(request, "authentication/login_form.html", {"form": form})


@patient_access_required
def patient_dashboard(request):
    patient_id = request.session.get("patient_id")
    if not patient_id:
        return redirect("authentication:patient_login")

    patient = get_object_or_404(Patient, id=patient_id)
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