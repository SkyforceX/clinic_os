from django.urls import path

from apps.catalogs.web.views import (
    category_create,
    category_delete,
    category_edit,
    category_list,
    group_create,
    group_delete,
    group_edit,
    group_list,
    package_create,
    package_delete,
    package_detail,
    package_edit,
    package_list,
)

app_name = "catalogs"

urlpatterns = [
    path("groups/", group_list, name="group_list"),
    path("groups/create/", group_create, name="group_create"),
    path("groups/<int:pk>/edit/", group_edit, name="group_edit"),
    path("groups/<int:pk>/delete/", group_delete, name="group_delete"),

    path("categories/", category_list, name="category_list"),
    path("categories/create/", category_create, name="category_create"),
    path("categories/<int:pk>/edit/", category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", category_delete, name="category_delete"),

    path("packages/", package_list, name="package_list"),
    path("packages/create/", package_create, name="package_create"),
    path("packages/<int:pk>/", package_detail, name="package_detail"),
    path("packages/<int:pk>/edit/", package_edit, name="package_edit"),
    path("packages/<int:pk>/delete/", package_delete, name="package_delete"),
]