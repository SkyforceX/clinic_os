from django.urls import path

from apps.dashboard.views import overview

app_name = "dashboard"

urlpatterns = [
    path("", overview, name="overview"),
]
