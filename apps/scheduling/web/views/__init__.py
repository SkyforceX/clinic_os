"""
Public view API của scheduling web layer.

scheduling app chỉ expose:
- schedule_table      — bảng lịch khám cho staff
- redistribute_slots  — phân bổ lại slot cho một hợp đồng
- approval_modal      — (stub) modal duyệt

Patient booking views (register_schedule, submit_registration, show_thank_you)
đã chuyển về apps.booking.web.views.
Shim tương thích còn trong public_booking_views.py nhưng KHÔNG export ra đây.
"""

from apps.scheduling.web.views.contract_schedule_views import (
    redistribute_slots,
    schedule_table,
)
from apps.scheduling.web.views.schedule_admin_views import (
    approval_modal,
)

__all__ = [
    "schedule_table",
    "redistribute_slots",
    "approval_modal",
]
