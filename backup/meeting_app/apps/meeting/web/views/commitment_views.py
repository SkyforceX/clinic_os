from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View

from apps.meeting.domain.exceptions import MeetingDomainError
from apps.meeting.services.manage_commitments import (
    AddCommitmentCommand,
    DeleteCommitmentCommand,
    UpdateCommitmentCommand,
    add_commitment,
    delete_commitment,
    update_commitment,
)


class CommitmentAddView(LoginRequiredMixin, View):
    def post(self, request, session_id: int):
        data = request.POST
        assignment_id = int(data["dept_assignment_id"]) if data.get("dept_assignment_id", "").isdigit() else None
        assignee_id = int(data["assignee_id"]) if data.get("assignee_id", "").isdigit() else None

        cmd = AddCommitmentCommand(
            session_id=session_id,
            actor=request.user,
            title=data.get("title", ""),
            dept_assignment_id=assignment_id,
            assignee_id=assignee_id,
            deadline=data.get("deadline") or None,
            description=data.get("description", ""),
        )
        try:
            add_commitment(cmd)
            messages.success(request, "Đã thêm cam kết.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)


class CommitmentUpdateView(LoginRequiredMixin, View):
    def post(self, request, session_id: int, commitment_id: int):
        data = request.POST
        assignee_id = int(data["assignee_id"]) if data.get("assignee_id", "").isdigit() else None

        cmd = UpdateCommitmentCommand(
            commitment_id=commitment_id,
            actor=request.user,
            title=data.get("title"),
            description=data.get("description"),
            assignee_id=assignee_id,
            deadline=data.get("deadline") or None,
            status=data.get("status"),
        )
        try:
            update_commitment(cmd)
            messages.success(request, "Đã cập nhật cam kết.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)


class CommitmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, session_id: int, commitment_id: int):
        cmd = DeleteCommitmentCommand(commitment_id=commitment_id, actor=request.user)
        try:
            delete_commitment(cmd)
            messages.success(request, "Đã xóa cam kết.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)
