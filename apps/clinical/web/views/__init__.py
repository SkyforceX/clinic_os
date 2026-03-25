from apps.clinical.web.views.assistant_views import load_fixture_data, sum_assistant
from apps.clinical.web.views.dashboard_views import clinical_dashboard
from apps.clinical.web.views.dental_views import (
    api_save_dental_exam,
    dental_exam_form,
    get_dental_data,
)
from apps.clinical.web.views.pathology_views import (
    get_pathology_data,
    pathology,
    pathology_detail,
    update_pathology_evaluation,
    upload_pathology_pdf,
)

__all__ = [
    "clinical_dashboard",
    "sum_assistant",
    "load_fixture_data",
    "dental_exam_form",
    "api_save_dental_exam",
    "get_dental_data",
    "pathology",
    "pathology_detail",
    "upload_pathology_pdf",
    "get_pathology_data",
    "update_pathology_evaluation",
]