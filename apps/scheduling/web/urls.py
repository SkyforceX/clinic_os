from django.urls import path

from apps.scheduling.web.views import add_holiday, add_special_exam_category, delete_holiday, delete_slot_registration_view, edit_special_exam_category, end_schedule, general_settings, get_slot_cleanup_data, get_slot_data, redistribute_slots, schedule_table, update_slot_capacities

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
    path("schedule-config/<int:config_id>/slot-cleanup-data/", get_slot_cleanup_data, name="get_slot_cleanup_data"),
    path("schedule-config/<int:config_id>/update-slots/", update_slot_capacities, name="update_slot_capacities"),
    path("slot-registrations/<int:appointment_id>/delete/", delete_slot_registration_view, name="delete_slot_registration"),
    path("contract/<int:contract_id>/redistribute/", redistribute_slots, name="redistribute_slots"),
    path("general-settings/", general_settings, name="general_settings"),
    path("holidays/add/", add_holiday, name="add_holiday"),
    path("holidays/<int:holiday_id>/delete/", delete_holiday, name="delete_holiday"),
    path("special-exam-categories/add/", add_special_exam_category, name="add_special_exam_category"),
    path("special-exam-categories/<int:category_id>/edit/", edit_special_exam_category, name="edit_special_exam_category"),

    path("", register_schedule, name="register_schedule"),
    path("submit-registration/", submit_registration, name="submit_registration"),
    path("thankyou/", show_thank_you, name="show_thank_you"),
]
