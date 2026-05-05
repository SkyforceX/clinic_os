# crm/apps/api_his/urls.py
from django.urls import path

from .view_api_tools import (
    ApiPlaygroundView,
    BookingHisPushDemoView,
    BookingHisPushSendView,
    BookingHisLocalLogView,
)
from .views import HisAppointmentListView


app_name = 'api_his'
urlpatterns = [
    path("v1/his/appointments/", HisAppointmentListView.as_view(), name="his-appointments"),
    path("tools/api-playground/", ApiPlaygroundView.as_view(), name="api_playground"),
    path("tools/booking-his-push/", BookingHisPushDemoView.as_view(), name="booking_his_push_demo"),
    path("tools/booking-his-push/send/", BookingHisPushSendView.as_view(), name="booking_his_push_send"),
    path("tools/booking-his-push/local-log/", BookingHisLocalLogView.as_view(), name="booking_his_local_log"),
]
