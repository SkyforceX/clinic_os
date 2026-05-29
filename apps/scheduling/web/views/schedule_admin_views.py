from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import PublicHoliday, SystemGeneralSetting
from apps.scheduling.models import SpecialExamCategory
from apps.scheduling.policies import SchedulingPolicy
from apps.scheduling.web.forms import PublicHolidayForm, SpecialExamCategoryForm, SystemGeneralSettingForm


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
    can_manage = SchedulingPolicy.can_manage_general_settings(request.user)
    can_manage_categories = SchedulingPolicy.can_manage_special_exam_categories(request.user)

    if not (can_manage or can_manage_categories):
        messages.error(request, "Bạn không có quyền vào mục Thiết lập chung.")
        return redirect("scheduling:schedule_table")

    setting = SystemGeneralSetting.get_solo()

    if request.method == "POST":
        if not can_manage:
            messages.error(request, "Bạn không có quyền cập nhật thiết lập slot.")
            return redirect("scheduling:general_settings")
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
    special_exam_categories = SpecialExamCategory.objects.all()

    return render(
        request,
        "scheduling/staff/general_settings.html",
        {
            "form": form,
            "setting": setting,
            "holidays": holidays,
            "holiday_form": holiday_form,
            "special_exam_categories": special_exam_categories,
            "can_manage_special_exam_categories": can_manage_categories,
            "category_form": SpecialExamCategoryForm(),
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


@login_required(login_url="authentication:staff_login")
@require_POST
def add_special_exam_category(request):
    if not SchedulingPolicy.can_manage_special_exam_categories(request.user):
        messages.error(request, "Bạn không có quyền tạo mục khám đặc biệt.")
        return redirect("scheduling:general_settings")

    form = SpecialExamCategoryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, f"Đã tạo danh mục: {form.cleaned_data['name']}.")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)

    return redirect("scheduling:general_settings")


@login_required(login_url="authentication:staff_login")
@require_POST
def edit_special_exam_category(request, category_id):
    if not SchedulingPolicy.can_manage_special_exam_categories(request.user):
        messages.error(request, "Bạn không có quyền sửa mục khám đặc biệt.")
        return redirect("scheduling:general_settings")

    category = get_object_or_404(SpecialExamCategory, pk=category_id)
    form = SpecialExamCategoryForm(request.POST, instance=category)
    if form.is_valid():
        form.save()
        messages.success(request, f"Đã cập nhật danh mục: {form.cleaned_data['name']}.")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)

    return redirect("scheduling:general_settings")