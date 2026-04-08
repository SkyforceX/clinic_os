from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalogs.models import (
    CheckupCategory,
    CheckupPackageTemplate,
    CheckupPackageTemplateItem,
    GroupCheckup,
)
from apps.catalogs.policies import CatalogPolicy
from apps.catalogs.web.forms import (
    CheckupCategoryForm,
    CheckupPackageTemplateForm,
    GroupCheckupForm,
)


def _deny(request):
    messages.error(request, "Bạn không có quyền truy cập chức năng này.")
    return redirect("contract:quotation_list")


@login_required(login_url="authentication:staff_login")
def group_list(request):
    if not CatalogPolicy.can_manage_groups(request.user):
        return _deny(request)

    query = (request.GET.get("q") or "").strip()
    groups = GroupCheckup.objects.all().order_by("display_order", "name", "id")
    if query:
        groups = groups.filter(Q(name__icontains=query) | Q(group_en__icontains=query))

    return render(
        request,
        "catalogs/staff/group_list.html",
        {
            "groups": groups,
            "query": query,
        },
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def group_create(request):
    if not CatalogPolicy.can_manage_groups(request.user):
        return _deny(request)

    form = GroupCheckupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã tạo nhóm khám.")
        return redirect("catalogs:group_list")

    return render(
        request,
        "catalogs/staff/group_form.html",
        {
            "form": form,
            "page_title": "Tạo nhóm khám",
            "submit_label": "Lưu nhóm",
        },
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def group_edit(request, pk):
    if not CatalogPolicy.can_manage_groups(request.user):
        return _deny(request)

    obj = get_object_or_404(GroupCheckup, pk=pk)
    form = GroupCheckupForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật nhóm khám.")
        return redirect("catalogs:group_list")

    return render(
        request,
        "catalogs/staff/group_form.html",
        {
            "form": form,
            "page_title": "Sửa nhóm khám",
            "submit_label": "Cập nhật nhóm",
            "object": obj,
        },
    )


@login_required(login_url="authentication:staff_login")
@require_POST
def group_delete(request, pk):
    if not CatalogPolicy.can_manage_groups(request.user):
        return _deny(request)

    obj = get_object_or_404(GroupCheckup, pk=pk)
    obj.delete()
    messages.success(request, "Đã xóa nhóm khám.")
    return redirect("catalogs:group_list")


@login_required(login_url="authentication:staff_login")
def category_list(request):
    if not CatalogPolicy.can_view_categories(request.user):
        return _deny(request)

    query = (request.GET.get("q") or "").strip()
    group_id = (request.GET.get("group_id") or "").strip()

    categories = (
        CheckupCategory.objects.select_related("group_checkup", "created_by", "updated_by")
        .all()
        .order_by("group_checkup__display_order", "group_checkup__name", "display_order", "id")
    )

    if query:
        categories = categories.filter(
            Q(item_name__icontains=query)
            | Q(item_code__icontains=query)
            | Q(description__icontains=query)
            | Q(subgroup_name__icontains=query)
            | Q(group_checkup__name__icontains=query)
        )

    if group_id.isdigit():
        categories = categories.filter(group_checkup_id=int(group_id))

    groups = GroupCheckup.objects.filter(is_active=True).order_by("display_order", "name", "id")

    return render(
        request,
        "catalogs/staff/category_list.html",
        {
            "categories": categories,
            "groups": groups,
            "query": query,
            "group_id": group_id,
        },
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def category_create(request):
    if not CatalogPolicy.can_manage_categories(request.user):
        return _deny(request)

    form = CheckupCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Đã tạo danh mục khám.")
        return redirect("catalogs:category_list")

    return render(
        request,
        "catalogs/staff/category_form.html",
        {
            "form": form,
            "page_title": "Tạo danh mục khám",
            "submit_label": "Lưu danh mục",
        },
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def category_edit(request, pk):
    if not CatalogPolicy.can_manage_categories(request.user):
        return _deny(request)

    obj = get_object_or_404(CheckupCategory, pk=pk)
    form = CheckupCategoryForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.updated_by = request.user
        updated.save()
        messages.success(request, "Đã cập nhật danh mục khám.")
        return redirect("catalogs:category_list")

    return render(
        request,
        "catalogs/staff/category_form.html",
        {
            "form": form,
            "page_title": "Sửa danh mục khám",
            "submit_label": "Cập nhật danh mục",
            "object": obj,
        },
    )


@login_required(login_url="authentication:staff_login")
@require_POST
def category_delete(request, pk):
    if not CatalogPolicy.can_manage_categories(request.user):
        return _deny(request)

    obj = get_object_or_404(CheckupCategory, pk=pk)
    obj.delete()
    messages.success(request, "Đã xóa danh mục khám.")
    return redirect("catalogs:category_list")


@login_required(login_url="authentication:staff_login")
def package_list(request):
    if not CatalogPolicy.can_view_packages(request.user):
        return _deny(request)

    query = (request.GET.get("q") or "").strip()

    packages = (
        CheckupPackageTemplate.objects.select_related("created_by", "updated_by")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=CheckupPackageTemplateItem.objects.select_related("category", "category__group_checkup")
                .order_by("display_order", "id"),
            )
        )
        .all()
        .order_by("-created_at", "-id")
    )

    if not CatalogPolicy.is_manager(request.user):
        packages = packages.filter(created_by=request.user)

    if query:
        packages = packages.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(created_by__username__icontains=query)
            | Q(created_by__first_name__icontains=query)
            | Q(created_by__last_name__icontains=query)
        )

    return render(
        request,
        "catalogs/staff/package_list.html",
        {
            "packages": packages,
            "query": query,
            "is_manager": CatalogPolicy.is_manager(request.user),
        },
    )


@login_required(login_url="authentication:staff_login")
def package_detail(request, pk):
    package = get_object_or_404(
        CheckupPackageTemplate.objects.select_related("created_by", "updated_by").prefetch_related(
            Prefetch(
                "items",
                queryset=CheckupPackageTemplateItem.objects.select_related("category", "category__group_checkup")
                .order_by("display_order", "id"),
            )
        ),
        pk=pk,
    )

    if not CatalogPolicy.can_edit_package(request.user, package) and not CatalogPolicy.is_manager(request.user):
        return _deny(request)

    grouped = []
    seen = {}

    for item in package.items.all():
        category = item.category
        group_name = category.group_checkup.name
        subgroup_name = category.subgroup_name or ""

        if group_name not in seen:
            seen[group_name] = {
                "group_name": group_name,
                "items": [],
                "subgroups": {},
            }
            grouped.append(seen[group_name])

        block = seen[group_name]
        if subgroup_name:
            block["subgroups"].setdefault(subgroup_name, []).append(category)
        else:
            block["items"].append(category)

    return render(
        request,
        "catalogs/staff/package_detail.html",
        {
            "package": package,
            "grouped_categories": grouped,
            "can_edit": CatalogPolicy.can_edit_package(request.user, package),
            "can_delete": CatalogPolicy.can_delete_package(request.user, package),
        },
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def package_create(request):
    if not CatalogPolicy.can_create_package(request.user):
        return _deny(request)

    form = CheckupPackageTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        package = form.save(created_by=request.user, updated_by=request.user)
        messages.success(request, "Đã tạo gói khám mẫu.")
        return redirect("catalogs:package_detail", pk=package.pk)

    return render(
        request,
        "catalogs/staff/package_form.html",
        {
            "form": form,
            "page_title": "Tạo gói khám mẫu",
            "submit_label": "Lưu gói khám",
            "grouped_categories": form.grouped_categories(),
        },
    )


@login_required(login_url="authentication:staff_login")
@require_http_methods(["GET", "POST"])
def package_edit(request, pk):
    package = get_object_or_404(CheckupPackageTemplate, pk=pk)
    if not CatalogPolicy.can_edit_package(request.user, package):
        return _deny(request)

    form = CheckupPackageTemplateForm(request.POST or None, instance=package)
    if request.method == "POST" and form.is_valid():
        package = form.save(updated_by=request.user)
        messages.success(request, "Đã cập nhật gói khám mẫu.")
        return redirect("catalogs:package_detail", pk=package.pk)

    return render(
        request,
        "catalogs/staff/package_form.html",
        {
            "form": form,
            "page_title": "Sửa gói khám mẫu",
            "submit_label": "Cập nhật gói khám",
            "object": package,
            "grouped_categories": form.grouped_categories(),
        },
    )


@login_required(login_url="authentication:staff_login")
@require_POST
def package_delete(request, pk):
    package = get_object_or_404(CheckupPackageTemplate, pk=pk)
    if not CatalogPolicy.can_delete_package(request.user, package):
        return _deny(request)

    package.delete()
    messages.success(request, "Đã xóa gói khám mẫu.")
    return redirect("catalogs:package_list")