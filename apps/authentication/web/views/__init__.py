from apps.authentication.web.views.password_reset_views import (
    verify_otp,
    reset_password,
    request_password_reset,
)
from apps.authentication.web.views.patient_auth_views import (
    patient_dashboard,
    patient_login,
    patient_logout,
)
from apps.authentication.web.views.staff_auth_views import (
    staff_login,
    staff_logout,
)

__all__ = [
    "staff_login",
    "staff_logout",
    "patient_login",
    "patient_dashboard",
    "patient_logout",
    "request_password_reset",
    "verify_otp",
    "reset_password",
]