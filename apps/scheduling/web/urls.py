from django.urls import path

from apps.scheduling.web.views import add_holiday, delete_holiday, end_schedule, general_settings, get_slot_data, get_us_modal_data, redistribute_slots, schedule_table, update_slot_capacities

from apps.scheduling.web.views.public_booking_views import (
    register_schedule,
    show_thank_you,
    submit_registration,
)

app_name = "scheduling"

urlpatterns = [
    path("schedule-table/", schedule_table, name="schedule_table"),
    path("schedule-config/<int:config_id>/end/", end_schedule, name="end_schedule"),
    path("schedule-config/<int:config_id>/slot-data/", get_slot_data, name="get_slot_data"),
    path("schedule-config/<int:config_id>/update-slots/", update_slot_capacities, name="update_slot_capacities"),
    path("contract/<int:contract_id>/redistribute/", redistribute_slots, name="redistribute_slots"),
    path("ultrasound-modal/", get_us_modal_data, name="ultrasound_modal"),
    path("general-settings/", general_settings, name="general_settings"),
    path("holidays/add/", add_holiday, name="add_holiday"),
    path("holidays/<int:holiday_id>/delete/", delete_holiday, name="delete_holiday"),

    path("", register_schedule, name="register_schedule"),
    path("submit-registration/", submit_registration, name="submit_registration"),
    path("thankyou/", show_thank_you, name="show_thank_you"),
]