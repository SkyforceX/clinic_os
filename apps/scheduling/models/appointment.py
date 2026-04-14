"""
Compatibility module.

Giữ import path `apps.scheduling.models.appointment.Appointment`
trong giai đoạn chuyển tiếp.
"""

from apps.booking.models import Appointment

__all__ = ["Appointment"]