"""
Public model API của app scheduling.

Scheduling chỉ quản lý slot lịch khám.
Booking/Appointment nằm ở apps.booking.
"""

from .schedule import ScheduleSlot, SlotStatus, SlotType, TimeShift

__all__ = [
    "ScheduleSlot",
    "SlotStatus",
    "SlotType",
    "TimeShift",
]