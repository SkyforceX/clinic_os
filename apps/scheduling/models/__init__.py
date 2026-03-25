"""
Transitional model facade for scheduling domain.

Ở bước refactor này:
- ScheduleSlot vẫn dùng bảng/model legacy của apps.booking.AppointmentSchedule
- Appointment vẫn dùng apps.booking.Appointment
- BloodCollectionPlan vẫn dùng apps.booking.BloodCollectionInfo
- TimeShift vẫn dùng enum cũ của booking
"""

from apps.booking.models import (
    Appointment,
    AppointmentSchedule as ScheduleSlot,
    BloodCollectionInfo as BloodCollectionPlan,
    TimeShift,
)

__all__ = [
    "Appointment",
    "ScheduleSlot",
    "BloodCollectionPlan",
    "TimeShift",
]