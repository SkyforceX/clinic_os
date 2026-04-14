# crm/apps/api_his/urls.py
from django.urls import path

from .view_api_tools import ApiPlaygroundView
from .views import HisAppointmentListView


app_name = 'api_his'
urlpatterns = [
    path("v1/his/appointments/", HisAppointmentListView.as_view(), name="his-appointments"),
    path("tools/api-playground/", ApiPlaygroundView.as_view(), name="api_playground"),
]
