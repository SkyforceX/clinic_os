from django.urls import path
from apps.retention.web.views.retention_views import at_risk_detail, retention_overview

app_name = "retention"

urlpatterns = [
    path("",        retention_overview, name="overview"),
    path("at-risk/", at_risk_detail,   name="at_risk"),
]
