"""
Compatibility shim.

File cũ từng bị kéo vào `apps.contract.utils`.
Giữ lại để tránh vỡ import trong giai đoạn chuyển tiếp.
"""

from apps.scheduling.web.views.contract_schedule_views import redistribute_slots

__all__ = [
    "redistribute_slots",
]