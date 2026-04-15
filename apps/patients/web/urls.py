from django.urls import path

from apps.patients.web.views.patient_views import (
    delete_patient_ajax,
    delete_patients_by_company,
    get_all_patients,
    get_patients_by_company,
    his_patient_sync_list,
    trigger_his_patient_sync,
    update_patient_ajax,
)

app_name = "patients"

urlpatterns = [
    path("his-sync/", his_patient_sync_list, name="his_patient_sync_list"),
    path("his-sync/trigger/", trigger_his_patient_sync, name="trigger_his_patient_sync"),

    path("all/", get_all_patients, name="get_all_patients"),
    path("by-company/<int:company_id>/", get_patients_by_company, name="get_patients_by_company"),
    path("<int:patient_id>/update-ajax/", update_patient_ajax, name="update_patient_ajax"),
    path("<int:patient_id>/delete-ajax/", delete_patient_ajax, name="delete_patient_ajax"),
    path("by-company/<int:company_id>/delete-all/", delete_patients_by_company, name="delete_patients_by_company"),
]