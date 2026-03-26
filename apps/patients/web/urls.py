from django.urls import path

from apps.patients.web.views.patient_views import (
    delete_patient_ajax,
    get_all_patients,
    get_patients_by_company,
    update_patient_ajax,
    delete_patients_by_company,
)

app_name = "patients"

urlpatterns = [
    path("all/", get_all_patients, name="get_all_patients"),
    path("by-company/<int:company_id>/", get_patients_by_company, name="get_patients_by_company"),
    path("<int:patient_id>/update-ajax/", update_patient_ajax, name="update_patient_ajax"),
    path("<int:patient_id>/delete-ajax/", delete_patient_ajax, name="delete_patient_ajax"),
    path("by-company/<int:company_id>/delete-all/", delete_patients_by_company, name="delete_patients_by_company"),
]