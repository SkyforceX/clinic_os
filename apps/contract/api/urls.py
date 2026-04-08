from django.urls import path

from apps.contract.api.views import ajax_checkup_overview, api_quotation_packages

app_name = "contract_api"

urlpatterns = [
    path("checkup-overview/", ajax_checkup_overview, name="ajax_checkup_overview"),
    path("quotation-packages/", api_quotation_packages, name="quotation_packages"),
]
