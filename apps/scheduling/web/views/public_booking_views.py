"""
Compatibility shim — patient booking views.

Các view đặt lịch của bệnh nhân đã được chuyển về canonical home:
    apps.booking.web.views.patient_booking_views

File này chỉ còn để các URL patterns cũ dùng namespace ``scheduling:``
(register_schedule, submit_registration, show_thank_you) không bị broken
trong giai đoạn chuyển tiếp.

Không thêm logic mới vào đây.
Xóa file này sau khi toàn bộ template/redirect đã dùng namespace ``booking:``.
"""

from apps.booking.web.views.patient_booking_views import (  # noqa: F401
    register_schedule,
    show_thank_you,
    submit_registration,
)
