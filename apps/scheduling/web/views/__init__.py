from apps.scheduling.web.views.contract_schedule_views import (
    redistribute_slots,
    schedule_table,
)
from apps.scheduling.web.views.schedule_admin_views import (
    approval_modal,
    general_settings,
)

__all__ = [
    "schedule_table",
    "redistribute_slots",
    "approval_modal",
    "general_settings",
]