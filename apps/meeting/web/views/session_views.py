from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.meeting.domain.enums import DEPARTMENT_CHOICES, MEETING_STEP_LABELS, MEETING_STEP_MAX
from apps.meeting.domain.exceptions import MeetingDomainError
from apps.meeting.models import MeetingSession
from apps.meeting.policies import MeetingPolicy
from apps.meeting.selectors import (
    get_session_dashboard,
    get_session_for_user,
    list_sessions_for_user,
)
from apps.meeting.services.create_session import CreateSessionCommand, execute as create_session
from apps.meeting.services.manage_session import (
    AdvanceStepCommand,
    CloseSessionCommand,
    advance_step,
    close_session,
)

User = get_user_model()
STEPS = list(MEETING_STEP_LABELS.items())


class SessionListView(LoginRequiredMixin, View):
    template_name = "meeting/staff/session_list.html"

    def get(self, request):
        sessions = list_sessions_for_user(request.user)
        return render(request, self.template_name, {"sessions": sessions})


class SessionCreateView(LoginRequiredMixin, View):
    template_name = "meeting/staff/session_form.html"

    def _context(self, form_data=None):
        # Active contracts với company
        try:
            from apps.contract.models.contract import Contract
            contracts = (
                Contract.objects
                .filter(status__in=("APPROVED", "ACTIVE"))
                .select_related("company")
                .order_by("-created_at")[:100]
            )
        except Exception:
            contracts = []

        # All companies
        try:
            from apps.organizations.models import Company
            companies = Company.objects.all().order_by("name")[:200]
        except Exception:
            companies = []

        # All active users
        all_users = (
            User.objects.filter(is_active=True)
            .select_related("employee_profile__department")
            .order_by("first_name", "last_name", "username")
        )

        return {
            "department_choices": DEPARTMENT_CHOICES,
            "contracts":          list(contracts),
            "companies":          list(companies),
            "all_users":          list(all_users),
            "form_data":          form_data,
            "meeting_steps":      STEPS,
        }

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        data        = request.POST
        dept_codes  = data.getlist("department_codes")
        participant_ids = [int(i) for i in data.getlist("participant_user_ids") if i.isdigit()]

        cmd = CreateSessionCommand(
            title=data.get("title", ""),
            meeting_date=data.get("meeting_date", ""),
            meeting_time=data.get("meeting_time") or None,
            location=data.get("location", ""),
            note=data.get("note", ""),
            contract_id=int(data["contract_id"]) if data.get("contract_id", "").isdigit() else None,
            company_id=int(data["company_id"])  if data.get("company_id",  "").isdigit() else None,
            department_codes=dept_codes,
            participant_user_ids=participant_ids,
            actor=request.user,
        )
        try:
            session = create_session(cmd)
            messages.success(request, f"Đã tạo buổi họp: {session.title}")
            return redirect("meeting:session_detail", session_id=session.pk)
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, self._context(form_data=data))


class SessionDetailView(LoginRequiredMixin, View):
    template_name = "meeting/staff/session_detail.html"

    def get(self, request, session_id: int):
        session = get_session_for_user(user=request.user, session_id=session_id)
        if session is None:
            raise Http404

        dashboard    = get_session_dashboard(session=session)
        can_edit     = MeetingPolicy.can_edit_session(request.user, session)
        can_advance  = MeetingPolicy.can_advance_step(request.user, session)
        can_sign     = MeetingPolicy.can_sign_minutes(request.user, session)
        already_signed = session.signatures.filter(user=request.user).exists()

        # All users for dropdowns
        all_users = (
            User.objects.filter(is_active=True)
            .select_related("employee_profile__department")
            .order_by("first_name", "last_name", "username")
        )

        return render(request, self.template_name, {
            "session":       session,
            "dashboard":     dashboard,
            "can_edit":      can_edit,
            "can_advance":   can_advance,
            "can_sign":      can_sign,
            "already_signed":already_signed,
            "all_users":     all_users,
            "steps":         STEPS,
        })


class StepAdvanceView(LoginRequiredMixin, View):
    def post(self, request, session_id: int):
        cmd = AdvanceStepCommand(session_id=session_id, actor=request.user)
        try:
            session = advance_step(cmd)
            messages.success(request, f"Chuyển sang bước {session.current_step}: {session.step_label}")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)


class SessionCloseView(LoginRequiredMixin, View):
    def post(self, request, session_id: int):
        force = request.POST.get("force") == "1"
        cmd   = CloseSessionCommand(session_id=session_id, actor=request.user, force=force)
        try:
            close_session(cmd)
            messages.success(request, "Đã đóng buổi họp và tạo tasks từ danh sách cam kết.")
        except MeetingDomainError as exc:
            messages.error(request, str(exc))
        return redirect("meeting:session_detail", session_id=session_id)
