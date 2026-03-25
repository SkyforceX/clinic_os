"""
Compatibility module.

Giữ import path `apps.scheduling.models.schedule.*`
trong giai đoạn chuyển tiếp.
"""

from apps.booking.models import (
    AppointmentSchedule as ScheduleSlot,
    BloodCollectionInfo as BloodCollectionPlan,
    TimeShift,
)

__all__ = [
    "ScheduleSlot",
    "BloodCollectionPlan",
    "TimeShift",
]