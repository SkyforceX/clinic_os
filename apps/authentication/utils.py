from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.authentication.selectors.session_selectors import get_current_patient_from_session


def _normalize_text(value):
    return str(value or "").strip().lower()


def _norm_gender(value):
    raw = str(value or "").strip()
    normalized = _normalize_text(value)

    male_values = {
        "nam",
        "male",
        "m",
        "1",
        "true",
        "boy",
    }
    female_values = {
        "nữ",
        "nu",
        "female",
        "f",
        "0",
        "false",
        "girl",
    }

    if normalized in male_values:
        return "Nam"
    if normalized in female_values:
        return "Nữ"
    return raw


def patient_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        patient = get_current_patient_from_session(request)
        if not patient:
            request.session.pop("patient_id", None)
            request.session.pop("his_patient_sync_id", None)
            request.session.pop("patient_code", None)
            request.session.pop("patient_name", None)
            request.session.pop("is_patient", None)
            messages.warning(request, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
            return redirect("authentication:patient_login")

        request.current_patient = patient
        return view_func(request, *args, **kwargs)

    return _wrapped_view
