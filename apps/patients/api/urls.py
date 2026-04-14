from django.urls import path

from apps.patients.api.views import (
    ajax_patient_list_json,
    create_patient_ajax,
    upload_list_patient,
)

app_name = "patients_api"

urlpatterns = [
    path(
        "ajax/patients-json/<int:company_id>/<int:contract_id>/",
        ajax_patient_list_json,
        name="ajax_patient_list_json",
    ),
    path("ajax/create/", create_patient_ajax, name="create_patient_ajax"),
    path("ajax/import/", upload_list_patient, name="upload_list_patient"),
]