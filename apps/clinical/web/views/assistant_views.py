import json

from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import Http404, JsonResponse
from django.shortcuts import render

from apps.clinical.policies import ClinicalPolicy


@login_required(login_url="authentication:staff_login")
def sum_assistant(request):
    if not ClinicalPolicy.can_use_sum_assistant(request.user):
        return render(
            request,
            "core/403.html",
            {"error_message": "Bạn không có quyền truy cập."},
            status=403,
        )
    return render(request, "clinic/staff/sum_assistant.html")


@login_required(login_url="authentication:staff_login")
def load_fixture_data(request):
    fixture_path = finders.find("clinic/fixtures/sum_assistant_data.json")
    if not fixture_path:
        raise Http404("Không tìm thấy sum_assistant_data.json")

    with open(fixture_path, "r", encoding="utf-8") as file_handler:
        data = json.load(file_handler)

    return JsonResponse(data, safe=False)