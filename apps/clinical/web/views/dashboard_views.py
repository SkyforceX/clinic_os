from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.clinical.policies import ClinicalPolicy
from apps.clinical.selectors.dashboard_selectors import build_dashboard_context


@login_required(login_url="authentication:staff_login")
def clinical_dashboard(request):
    context = build_dashboard_context(request=request)
    if not ClinicalPolicy.can_view_dashboard(request.user):
        context["staff"] = None
    return render(request, "clinical/staff/dashboard.html", context)