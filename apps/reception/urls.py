from django.urls import path

from apps.reception import views
from apps.reception.views_stats import (
    checkin_stats,
    checkin_stats_api,
    patient_list_api,
)

app_name = "reception"

urlpatterns = [
    # Check-in tool (standalone, own auth)
    path("",           views.checkin_tool, name="checkin_tool"),
    path("lookup/",    views.ajax_lookup,  name="ajax_lookup"),
    path("action/",    views.ajax_action,  name="ajax_action"),
    path("stats/",     views.ajax_stats,   name="ajax_stats"),

    # Statistics (staff login required)
    path("thong-ke/",              checkin_stats,     name="checkin_stats"),
    path("thong-ke/api/",          checkin_stats_api, name="checkin_stats_api"),
    path("thong-ke/patient-list/", patient_list_api,  name="patient_list_api"),
]
