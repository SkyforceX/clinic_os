from django.urls import path

from apps.analytics.web.views.dashboard_views import overview, service_stats

app_name = "analytics"

urlpatterns = [
    path("", overview, name="overview"),
    path("services/", service_stats, name="service_stats"),
]
