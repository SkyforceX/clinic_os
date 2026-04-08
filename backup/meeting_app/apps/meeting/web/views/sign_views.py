from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.meeting.domain.exceptions import MeetingDomainError
from apps.meeting.models import MeetingSession
from apps.meeting.selectors import get_session_for_user
from apps.meeting.services.sign_minutes import SignMinutesCommand, sign_meeting_minutes


class SignMinutesView(LoginRequiredMixin, View):
    def post(self, request, session_id: int):
        cmd = SignMinutesCommand(
            session_id=session_id,
            actor=request.user,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            department=request.POST.get("department", ""),
            role_label=request.POST.get("role_label", ""),
        )
        try:
            sign_meeting_minutes(cmd)
            messages.success(request, "Đã ký biên bản thành công.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)


class MinutesPdfView(LoginRequiredMixin, View):
    """
    Render PDF biên bản họp.
    Sử dụng WeasyPrint — cần cài: pip install weasyprint
    Template: meeting/staff/minutes_pdf.html
    """

    def get(self, request, session_id: int):
        session = get_session_for_user(user=request.user, session_id=session_id)
        if session is None:
            from django.http import Http404
            raise Http404

        try:
            from django.template.loader import render_to_string
            from weasyprint import HTML

            html_string = render_to_string(
                "meeting/staff/minutes_pdf.html",
                {
                    "session": session,
                    "commitments": session.commitments.select_related("assignee", "dept_assignment").all(),
                    "signatures": session.signatures.select_related("user").all(),
                    "dept_assignments": session.dept_assignments.select_related("lead_user")
                    .prefetch_related("staff_shifts__user")
                    .all(),
                },
                request=request,
            )
            pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf()
            filename = f"bien_ban_hop_{session.pk}_{session.meeting_date}.pdf"
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response

        except ImportError:
            # Fallback: trả HTML nếu WeasyPrint chưa cài
            from django.template.loader import render_to_string
            from django.http import HttpResponse
            html = render_to_string(
                "meeting/staff/minutes_pdf.html",
                {"session": session},
                request=request,
            )
            return HttpResponse(html)


def _get_client_ip(request) -> str:
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
