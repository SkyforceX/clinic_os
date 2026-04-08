from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.meeting.domain.exceptions import MeetingDomainError
from apps.meeting.models import DeptAssignment, StaffShift
from apps.meeting.services.manage_session import (
    AddStaffShiftCommand,
    ConfirmDeptCommand,
    RemoveStaffShiftCommand,
    UnconfirmDeptCommand,
    add_staff_shift,
    confirm_dept_assignment,
    remove_staff_shift,
    unconfirm_dept_assignment,
)


class DeptConfirmView(LoginRequiredMixin, View):
    def post(self, request, session_id: int, assignment_id: int):
        cmd = ConfirmDeptCommand(assignment_id=assignment_id, actor=request.user)
        try:
            a = confirm_dept_assignment(cmd)
            messages.success(request, f"Đã xác nhận phân công: {a.dept_label}")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)


class DeptUnconfirmView(LoginRequiredMixin, View):
    def post(self, request, session_id: int, assignment_id: int):
        cmd = UnconfirmDeptCommand(assignment_id=assignment_id, actor=request.user)
        try:
            unconfirm_dept_assignment(cmd)
            messages.info(request, "Đã rút xác nhận phân công.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)


class ShiftAddView(LoginRequiredMixin, View):
    def post(self, request, session_id: int, assignment_id: int):
        data = request.POST
        user_id = int(data.get("user_id", 0) or 0)
        cmd = AddStaffShiftCommand(
            assignment_id=assignment_id,
            user_id=user_id,
            actor=request.user,
            role_in_day=data.get("role_in_day", ""),
            shift=data.get("shift", "FULL"),
            time_from=data.get("time_from") or None,
            time_to=data.get("time_to") or None,
            note=data.get("note", ""),
        )
        try:
            add_staff_shift(cmd)
            messages.success(request, "Đã thêm nhân viên vào ca.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)


class ShiftRemoveView(LoginRequiredMixin, View):
    def post(self, request, session_id: int, assignment_id: int, shift_id: int):
        cmd = RemoveStaffShiftCommand(shift_id=shift_id, actor=request.user)
        try:
            remove_staff_shift(cmd)
            messages.success(request, "Đã xóa ca làm việc.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)
