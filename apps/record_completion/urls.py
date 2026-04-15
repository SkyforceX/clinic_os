from django.urls import path

from apps.record_completion.web.views.pipeline_views import (
    advance_step_view,
    company_list_view,
    log_timeline_view,
    pipeline_view,
    return_step_view,
)

app_name = "record_completion"

urlpatterns = [
    path("", company_list_view, name="company_list"),
    path("company/<int:company_id>/", pipeline_view, name="pipeline"),
    path("<int:completion_id>/advance/", advance_step_view, name="advance_step"),
    path("<int:completion_id>/return/",  return_step_view,  name="return_step"),
    path("<int:completion_id>/logs/",    log_timeline_view, name="log_timeline"),
]
