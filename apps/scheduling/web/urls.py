from django.urls import path

from apps.scheduling.web.views import general_settings, redistribute_slots, schedule_table

from apps.scheduling.web.views.public_booking_views import (
    register_schedule,
    show_thank_you,
    submit_registration,
)

app_name = "scheduling"

urlpatterns = [
    path("schedule-table/", schedule_table, name="schedule_table"),
    path("contract/<int:contract_id>/redistribute/", redistribute_slots, name="redistribute_slots"),
    path("general-settings/", general_settings, name="general_settings"),

    path("", register_schedule, name="register_schedule"),
    path("submit-registration/", submit_registration, name="submit_registration"),
    path("thankyou/", show_thank_you, name="show_thank_you"),
]