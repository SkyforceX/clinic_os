from apps.scheduling.web.views.contract_schedule_views import (
    end_schedule,
    get_slot_data,
    get_us_modal_data,
    redistribute_slots,
    schedule_table,
    update_slot_capacities,
)
from apps.scheduling.web.views.schedule_admin_views import (
    add_holiday,
    approval_modal,
    delete_holiday,
    general_settings,
)

__all__ = [
    "schedule_table",
    "end_schedule",
    "redistribute_slots",
    "get_slot_data",
    "get_us_modal_data",
    "update_slot_capacities",
    "approval_modal",
    "general_settings",
    "add_holiday",
    "delete_holiday",
]