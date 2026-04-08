from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render

from apps.core.models import SystemGeneralSetting
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.web.forms import SystemGeneralSettingForm


def approval_modal(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    return JsonResponse(
        {
            "success": False,
            "message": "Màn hình approval modal chưa được triển khai trong bước refactor này.",
        },
        status=501,
    )


@login_required(login_url="authentication:staff_login")
def general_settings(request):
    if not SchedulingPolicy.can_manage_general_settings(request.user):
        messages.error(request, "Bạn không có quyền vào mục Thiết lập chung.")
        return redirect("scheduling:schedule_table")

    setting = SystemGeneralSetting.get_solo()

    if request.method == "POST":
        form = SystemGeneralSettingForm(request.POST, instance=setting)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, "Đã cập nhật thiết lập chung.")
            return redirect("scheduling:general_settings")
    else:
        form = SystemGeneralSettingForm(instance=setting)

    return render(
        request,
        "scheduling/staff/general_settings.html",
        {
            "form": form,
            "setting": setting,
        },
    )