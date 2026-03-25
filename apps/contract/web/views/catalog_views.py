from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.booking.models import CheckupCategory, GroupCheckup
from apps.contract.web.forms import CheckupCategoryForm, GroupCheckupForm


@login_required(login_url="authentication:staff_login")
def demo_api(request):
    return render(request, "contract/staff/demo_api.html")


@login_required(login_url="authentication:staff_login")
def groupcheckup_create(request):
    if request.method == "POST":
        form = GroupCheckupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã tạo nhóm khám.")
            return redirect("contract:create_proposal")
    else:
        form = GroupCheckupForm()

    return render(request, "contract/staff/groupcheckup_form.html", {"form": form})


@login_required(login_url="authentication:staff_login")
def checkupcategory_create(request):
    if request.method == "POST":
        form = CheckupCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã tạo danh mục khám.")
            return redirect("contract:create_proposal")
    else:
        form = CheckupCategoryForm()

    return render(request, "contract/staff/checkupcategory_form.html", {"form": form})


@login_required(login_url="authentication:staff_login")
def checkupcategory_edit(request, pk):
    instance = get_object_or_404(CheckupCategory, pk=pk)

    if request.method == "POST":
        form = CheckupCategoryForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật danh mục khám.")
            return redirect("contract:create_proposal")
    else:
        form = CheckupCategoryForm(instance=instance)

    return render(
        request,
        "contract/staff/checkupcategory_form.html",
        {
            "form": form,
            "instance": instance,
        },
    )