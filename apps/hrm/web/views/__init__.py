from apps.hrm.web.views.employee_views import (
    employee_list,
    employee_detail,
    employee_create,
    employee_edit,
    employee_transfer,
    employee_offboard,
)
from apps.hrm.web.views.department_views import (
    department_list,
    department_create,
    department_edit,
    position_list,
    position_create,
    position_edit,
)
from apps.hrm.web.views.doctor_schedule_views import (
    doctor_schedule_list,
    doctor_schedule_edit,
    doctor_schedule_bulk_save,
)

__all__ = [
    "employee_list", "employee_detail", "employee_create",
    "employee_edit", "employee_transfer", "employee_offboard",
    "department_list", "department_create", "department_edit",
    "position_list", "position_create", "position_edit",
    "doctor_schedule_list", "doctor_schedule_edit", "doctor_schedule_bulk_save",
]
