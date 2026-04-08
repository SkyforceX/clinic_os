from django.urls import path

from apps.meeting.web.views import (
    commitment_views,
    dept_views,
    session_views,
    sign_views,
)

app_name = "meeting"

urlpatterns = [
    # ── Session list & create ─────────────────────────────────────────────
    path("", session_views.SessionListView.as_view(), name="session_list"),
    path("create/", session_views.SessionCreateView.as_view(), name="session_create"),

    # ── Session detail / edit ─────────────────────────────────────────────
    path("<int:session_id>/", session_views.SessionDetailView.as_view(), name="session_detail"),
    path("<int:session_id>/close/", session_views.SessionCloseView.as_view(), name="session_close"),
    path("<int:session_id>/step/advance/", session_views.StepAdvanceView.as_view(), name="step_advance"),

    # ── DeptAssignment ────────────────────────────────────────────────────
    path("<int:session_id>/dept/<int:assignment_id>/confirm/",
         dept_views.DeptConfirmView.as_view(), name="dept_confirm"),
    path("<int:session_id>/dept/<int:assignment_id>/unconfirm/",
         dept_views.DeptUnconfirmView.as_view(), name="dept_unconfirm"),
    path("<int:session_id>/dept/<int:assignment_id>/shifts/add/",
         dept_views.ShiftAddView.as_view(), name="shift_add"),
    path("<int:session_id>/dept/<int:assignment_id>/shifts/<int:shift_id>/remove/",
         dept_views.ShiftRemoveView.as_view(), name="shift_remove"),

    # ── Commitments ───────────────────────────────────────────────────────
    path("<int:session_id>/commitments/add/",
         commitment_views.CommitmentAddView.as_view(), name="commitment_add"),
    path("<int:session_id>/commitments/<int:commitment_id>/update/",
         commitment_views.CommitmentUpdateView.as_view(), name="commitment_update"),
    path("<int:session_id>/commitments/<int:commitment_id>/delete/",
         commitment_views.CommitmentDeleteView.as_view(), name="commitment_delete"),

    # ── Signing & minutes ─────────────────────────────────────────────────
    path("<int:session_id>/sign/", sign_views.SignMinutesView.as_view(), name="sign_minutes"),
    path("<int:session_id>/minutes.pdf", sign_views.MinutesPdfView.as_view(), name="minutes_pdf"),
]
