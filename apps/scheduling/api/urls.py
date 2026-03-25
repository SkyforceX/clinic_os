from django.urls import path

from apps.scheduling.api.views import schedule_summary_json

app_name = "scheduling_api"

urlpatterns = [
    path("summary/", schedule_summary_json, name="schedule_summary_json"),
]