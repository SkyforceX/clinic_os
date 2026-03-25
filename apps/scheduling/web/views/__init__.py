from apps.scheduling.web.views.contract_schedule_views import (
    redistribute_slots,
    schedule_table,
)
from apps.scheduling.web.views.public_booking_views import (
    register_schedule,
    show_thank_you,
    submit_registration,
)
from apps.scheduling.web.views.schedule_admin_views import (
    approval_modal,
)

__all__ = [
    "schedule_table",
    "redistribute_slots",
    "register_schedule",
    "submit_registration",
    "show_thank_you",
    "approval_modal",
]