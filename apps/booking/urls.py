from django.urls import path

from . import views

app_name = "booking"

urlpatterns = [
    path("tao-lich-kham", views.appointment, name="appointment"),
    path("appointment/save", views.save_appointment, name="save_appointment"),
    path("schedule-table", views.schedule_table, name="schedule_table"),
    path("contract/<int:contract_id>/redistribute/", views.redistribute_slots, name="redistribute_slots"),
    path("appointment/approve/<int:contract_id>/", views.approve_contract, name="approve_contract"),
    path("appointment/delete_<int:contract_id>", views.delete_appointment, name="delete_appointment"),
    path("", views.register_schedule, name="register_schedule"),
    path("submit-registration/", views.submit_registration, name="submit_registration"),
    path("thankyou/", views.show_thank_you, name="show_thank_you"),
]