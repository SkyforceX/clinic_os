from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

@method_decorator(login_required(login_url='authentication:staff_login'), name='dispatch')
@method_decorator(staff_member_required, name='dispatch')
class ApiPlaygroundView(TemplateView):
    template_name = "tools/api_playground.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["default_endpoint"] = "/api/v1/his/appointments/"
        return ctx
