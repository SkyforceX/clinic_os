"""
URL patterns cho scheduling app.

Nhóm 1 — Schedule admin (canonical):
    schedule-table/                  scheduling:schedule_table
    contract/<id>/redistribute/      scheduling:redistribute_slots

Nhóm 2 — Patient booking shims (tương thích ngược):
    ""                               scheduling:register_schedule   → booking view
    submit-registration/             scheduling:submit_registration → booking view
    thankyou/                        scheduling:show_thank_you      → booking view

Khi toàn bộ template và link đã dùng namespace ``booking:``,
xóa nhóm 2 và file public_booking_views.py.
"""

from django.urls import path

from apps.scheduling.web.views import redistribute_slots, schedule_table

# shim import — không re-export, chỉ dùng cục bộ cho URL
from apps.scheduling.web.views.public_booking_views import (
    register_schedule,
    show_thank_you,
    submit_registration,
)

app_name = "scheduling"

urlpatterns = [
    # --- admin / slot management ---
    path("schedule-table/",                       schedule_table,      name="schedule_table"),
    path("contract/<int:contract_id>/redistribute/", redistribute_slots, name="redistribute_slots"),

    # --- patient booking shims (backward-compat) ---
    # TODO: xóa sau khi đã migrate URL names → booking namespace
    path("",                   register_schedule,  name="register_schedule"),
    path("submit-registration/", submit_registration, name="submit_registration"),
    path("thankyou/",           show_thank_you,     name="show_thank_you"),
]
