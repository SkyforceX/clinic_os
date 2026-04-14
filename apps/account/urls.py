from django.urls import path

from . import views

app_name = "account"

urlpatterns = [
    path("", views.patient_profile, name="patient_profile"),
    path("change-password/", views.change_password, name="change_password"),
]