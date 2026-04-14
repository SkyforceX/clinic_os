from django.urls import path

from apps.organizations.web.views.company_views import (
    company_create_view,
    company_delete_view,
    company_list_view,
    company_options_json,
    company_update_view,
)

app_name = "organizations"

urlpatterns = [
    path("companies/", company_list_view, name="company_list"),
    path("companies/create/", company_create_view, name="company_create"),
    path("companies/<int:company_id>/update/", company_update_view, name="company_update"),
    path("companies/<int:company_id>/delete/", company_delete_view, name="company_delete"),
    path("ajax/companies/options/", company_options_json, name="company_options_json"),
]