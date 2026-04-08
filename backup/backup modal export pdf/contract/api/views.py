from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.contract.selectors.checkup_overview import build_checkup_overview_payload


@login_required(login_url="authentication:staff_login")
@require_POST
def ajax_checkup_overview(request):
    company_id = request.POST.get("company_id")
    if not company_id:
        return JsonResponse({"success": False, "error": "Thiếu company_id"}, status=400)

    payload = build_checkup_overview_payload(user=request.user, company_id=company_id)
    return JsonResponse(payload)