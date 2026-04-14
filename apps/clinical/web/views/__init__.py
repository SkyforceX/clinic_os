from apps.clinical.web.views.assistant_views import load_fixture_data, sum_assistant
from apps.clinical.web.views.dashboard_views import clinical_dashboard
from apps.clinical.web.views.dental_views import (
    dental_exam_form,
    dental_exam_history,
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
    "dental_exam_form",
    "dental_exam_history",
    "get_dental_data",
    "get_pathology_data",
    "load_fixture_data",
    "pathology",
    "pathology_detail",
    "sum_assistant",
    "update_pathology_evaluation",
    "upload_pathology_pdf",
]