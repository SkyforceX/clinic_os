"""
URL patterns cho booking app.

Nhóm 1 — Patient booking (canonical, namespace ``booking:``):
    ""                     booking:register_schedule
    submit-registration/   booking:submit_registration
    thankyou/              booking:show_thank_you

Nhóm 2 — Staff / legacy (còn giữ để không break template cũ):
    tao-lich-kham          booking:appointment  (form tạo lịch hẹn thủ công)
    register-task/         booking:register_task

Các route sau đã được CHUYỂN sang app tương ứng và XÓA khỏi đây:
    appointment/save           → contract:save_contract
    appointment/approve/<id>/  → contract:approve_contract
    appointment/delete_<id>    → contract:delete_contract
    schedule-table             → scheduling:schedule_table
    contract/<id>/redistribute/→ scheduling:redistribute_slots
"""

from django.urls import path

from apps.booking import views as booking_views
from apps.booking.web.views import (
    register_schedule,
    show_thank_you,
    submit_registration,
)

app_name = "booking"

urlpatterns = [
    # --- patient booking (canonical) ---
    path("",                     register_schedule,   name="register_schedule"),
    path("submit-registration/", submit_registration, name="submit_registration"),
    path("thankyou/",            show_thank_you,      name="show_thank_you"),

    # --- staff / legacy ---
    path("tao-lich-kham",  booking_views.appointment,   name="appointment"),
    path("register-task/", booking_views.register_task, name="register_task"),
]
