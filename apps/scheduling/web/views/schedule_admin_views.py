from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import PublicHoliday, SystemGeneralSetting
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.web.forms import PublicHolidayForm, SystemGeneralSettingForm


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

    holidays = PublicHoliday.objects.all()
    holiday_form = PublicHolidayForm()

    return render(
        request,
        "scheduling/staff/general_settings.html",
        {
            "form": form,
            "setting": setting,
            "holidays": holidays,
            "holiday_form": holiday_form,
        },
    )


@login_required(login_url="authentication:staff_login")
@require_POST
def add_holiday(request):
    if not SchedulingPolicy.can_manage_general_settings(request.user):
        messages.error(request, "Bạn không có quyền thêm ngày nghỉ.")
        return redirect("scheduling:general_settings")

    form = PublicHolidayForm(request.POST)
    if form.is_valid():
        form.save()
        date_str = form.cleaned_data["date"].strftime("%d/%m/%Y")
        messages.success(request, f"Đã thêm ngày nghỉ {date_str}.")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)

    return redirect("scheduling:general_settings")


@login_required(login_url="authentication:staff_login")
@require_POST
def delete_holiday(request, holiday_id):
    if not SchedulingPolicy.can_manage_general_settings(request.user):
        messages.error(request, "Bạn không có quyền xóa ngày nghỉ.")
        return redirect("scheduling:general_settings")

    try:
        holiday = PublicHoliday.objects.get(pk=holiday_id)
        date_str = holiday.date.strftime("%d/%m/%Y")
        holiday.delete()
        messages.success(request, f"Đã xóa ngày nghỉ {date_str}.")
    except PublicHoliday.DoesNotExist:
        messages.error(request, "Không tìm thấy ngày nghỉ.")

    return redirect("scheduling:general_settings")