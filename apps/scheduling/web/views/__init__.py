from apps.scheduling.web.views.contract_schedule_views import (
    delete_slot_registration_view,
    end_schedule,
    get_slot_cleanup_data,
    get_slot_data,
    redistribute_slots,
    schedule_table,
    update_slot_capacities,
)
from apps.scheduling.web.views.schedule_admin_views import (
    add_holiday,
    add_special_exam_category,
    approval_modal,
    delete_holiday,
    edit_special_exam_category,
    general_settings,
)

__all__ = [
    "schedule_table",
    "end_schedule",
    "redistribute_slots",
    "get_slot_cleanup_data",
    "delete_slot_registration_view",
    "get_slot_data",
    "update_slot_capacities",
    "approval_modal",
    "general_settings",
    "add_holiday",
    "delete_holiday",
    "add_special_exam_category",
    "edit_special_exam_category",
]
