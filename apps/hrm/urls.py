"""
PATCH: thêm vào apps/hrm/urls.py (cuối urlpatterns)

Thêm 3 import và 3 path mới:
"""

# ── IMPORTS CẦN THÊM vào đầu file urls.py ──────────────────────────────
# from apps.hrm.web.views.work_schedule_views import (
#     work_schedule_month,
#     work_schedule_set_shift,
#     work_schedule_log,
# )

# ── PATHS CẦN THÊM vào urlpatterns ─────────────────────────────────────
# path("work-schedule/",          work_schedule_month,     name="work_schedule_month"),
# path("work-schedule/set-shift/",work_schedule_set_shift, name="work_schedule_set_shift"),
# path("work-schedule/log/",      work_schedule_log,       name="work_schedule_log"),


# ══════════════════════════════════════════════════════════════════════════
# FILE HOÀN CHỈNH (copy-paste toàn bộ để thay thế hrm/urls.py)
# ══════════════════════════════════════════════════════════════════════════

from django.urls import path

from apps.hrm.web.views import (
    department_create,
    department_edit,
    department_list,
    doctor_schedule_bulk_save,
    doctor_schedule_edit,
    doctor_schedule_list,
    employee_create,
    employee_detail,
    employee_edit,
    employee_list,
    employee_offboard,
    employee_transfer,
    position_create,
    position_edit,
    position_list,
)
from apps.hrm.web.views.work_schedule_views import (
    work_schedule_month,
    work_schedule_set_shift,
    work_schedule_log,
)

app_name = "hrm"

urlpatterns = [
    # ── Nhân viên ─────────────────────────────────────────────────────────────
    path("employees/",                              employee_list,     name="employee_list"),
    path("employees/create/",                       employee_create,   name="employee_create"),
    path("employees/<int:employee_id>/",            employee_detail,   name="employee_detail"),
    path("employees/<int:employee_id>/edit/",       employee_edit,     name="employee_edit"),
    path("employees/<int:employee_id>/transfer/",   employee_transfer, name="employee_transfer"),
    path("employees/<int:employee_id>/offboard/",   employee_offboard, name="employee_offboard"),

    # ── Phòng ban ─────────────────────────────────────────────────────────────
    path("departments/",                             department_list,   name="department_list"),
    path("departments/create/",                      department_create, name="department_create"),
    path("departments/<int:department_id>/edit/",    department_edit,   name="department_edit"),

    # ── Chức vụ ───────────────────────────────────────────────────────────────
    path("positions/",                              position_list,   name="position_list"),
    path("positions/create/",                       position_create, name="position_create"),
    path("positions/<int:position_id>/edit/",       position_edit,   name="position_edit"),

    # ── Lịch làm việc bác sĩ (cũ – giữ nguyên) ──────────────────────────────
    path("doctor-schedules/",                                           doctor_schedule_list,      name="doctor_schedule_list"),
    path("doctor-schedules/edit/",                                      doctor_schedule_edit,      name="doctor_schedule_edit"),
    path("doctor-schedules/edit/<str:week_start_str>/",                 doctor_schedule_edit,      name="doctor_schedule_edit_week"),
    path("doctor-schedules/edit/<str:week_start_str>/<int:doctor_id>/", doctor_schedule_edit,      name="doctor_schedule_edit_doctor"),
    path("doctor-schedules/bulk-save/",                                 doctor_schedule_bulk_save, name="doctor_schedule_bulk_save"),

    # ── Lịch làm việc toàn phòng khám (MỚI) ──────────────────────────────────
    path("work-schedule/",           work_schedule_month,     name="work_schedule_month"),
    path("work-schedule/set-shift/", work_schedule_set_shift, name="work_schedule_set_shift"),
    path("work-schedule/log/",       work_schedule_log,       name="work_schedule_log"),
]
