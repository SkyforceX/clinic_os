from django.urls import path

from apps.clinical.web.views import (
    clinical_dashboard,
    dental_exam_form,
    dental_exam_history,
    get_dental_data,
    get_pathology_data,
    load_fixture_data,
    pathology,
    pathology_detail,
    sum_assistant,
    update_pathology_evaluation,
    upload_pathology_pdf,
)

app_name = "clinical"

urlpatterns = [
    path("dashboard/", clinical_dashboard, name="clinical_dashboard"),
    path("sum-assistant/", sum_assistant, name="sum_assistant"),
    path("load-fixture-data/", load_fixture_data, name="load_fixture_data"),

    # Dental exam — form + lưu (POST) + lịch sử
    path("dental-exam/", dental_exam_form, name="dental_exam_form"),
    path("api/dental-exam-history/<int:patient_id>/", dental_exam_history, name="dental_exam_history"),
    path("get_dental_data/<int:patient_id>/", get_dental_data, name="get_dental_data"),

    # Pathology
    path("pathology/", pathology, name="pathology"),
    path("pathology-detail/", pathology_detail, name="pathology_detail"),
    path("upload-pathology/", upload_pathology_pdf, name="upload_pathology_pdf"),
    path("get_pathology_data/<int:patient_id>/", get_pathology_data, name="get_pathology_data"),
    path("update_pathology_evaluation/", update_pathology_evaluation, name="update_pathology_evaluation"),
]