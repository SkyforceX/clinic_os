from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView


def _can_access_api_playground(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_staff", False):
        return True
    return user.groups.filter(
        name__in=["Executive", "Executives", "IT Admin", "IT", "IT Support"]
    ).exists()


@method_decorator(login_required(login_url='authentication:staff_login'), name='dispatch')
class ApiPlaygroundView(TemplateView):
    template_name = "tools/api_playground.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        if not _can_access_api_playground(request.user):
            raise PermissionDenied
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["default_endpoint"] = "/api/v1/his/appointments/"
        return ctx
