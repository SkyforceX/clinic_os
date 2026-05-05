from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


AI_ASSISTANT_ALLOWED_GROUPS = getattr(
    settings,
    "AI_ASSISTANT_ALLOWED_GROUPS",
    [
        "Executives",
        "Executive",
        "Managers",
        "Manager",
        "Quality",
        "HR Admins",
        "HR Admin",
        "Sales Team",
        "Doctors",
        "Nurses",
        "Accountants",
        "Lab Technicians",
        "Imaging Technicians",
        "Operations Team",
        "IT Staff",
        "IT Admin",
        "Customer Service Team",
    ],
)

MANAGER_ASSISTANT_ALLOWED_GROUPS = {
    "Executives",
    "Executive",
    "Managers",
    "Manager",
    "IT Admin",
}


def _has_group(user, allowed_names: set[str]) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return user.groups.filter(name__in=allowed_names).exists()


def user_can_access_ai(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return user.groups.filter(name__in=AI_ASSISTANT_ALLOWED_GROUPS).exists()


def can_use_ai_assistant(user):
    return user_can_access_ai(user)


def can_access_staff_assistant(user):
    return user_can_access_ai(user)


def can_access_manager_assistant(user):
    return _has_group(user, MANAGER_ASSISTANT_ALLOWED_GROUPS)


def can_access_customer_assistant(user=None):
    return True


def can_access_clinical_context(user):
    return _has_group(
        user,
        {
            "Doctors",
            "Nurses",
            "Lab Technicians",
            "Imaging Technicians",
            "Quality",
        },
    )


def can_access_patient_context(user, patient_id=None):
    return can_access_clinical_context(user)


def can_access_contract_context(user, contract_id=None):
    return _has_group(
        user,
        {
            "Executives",
            "Executive",
            "Managers",
            "Manager",
            "Sales Team",
        },
    )


class AiAssistantAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        if not user_can_access_ai(request.user):
            raise PermissionDenied
        return response


class StaffAssistantAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        if not can_access_staff_assistant(request.user):
            raise PermissionDenied
        return response


class ManagerAssistantAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        if not can_access_manager_assistant(request.user):
            raise PermissionDenied
        return response
