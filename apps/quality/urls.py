# apps/quality/urls.py
from django.urls import path
from .views import (
    MedicalRecordAuditListView,
    MedicalRecordAuditCreateView,
    MedicalRecordAuditUpdateView,
    MedicalRecordAuditPrintPdfView,
    IncidentReportListView,
    IncidentReportCreateView,
    IncidentReportUpdateView,
    IncidentReportPrintPdfView,
    IncidentReportPublicCreateView,
    IncidentReportThanksView
)

app_name = "quality"

urlpatterns = [
    # Bảng kiểm tra HSBA
    path(
        "audits/medical-record/",
        MedicalRecordAuditListView.as_view(),
        name="medical_record_audit_list",
    ),
    path(
        "audits/medical-record/new/",
        MedicalRecordAuditCreateView.as_view(),
        name="medical_record_audit_create",
    ),
    path(
        "audits/medical-record/<int:pk>/edit/",
        MedicalRecordAuditUpdateView.as_view(),
        name="medical_record_audit_update",
    ),
    path(
        "audits/medical-record/<int:pk>/print/",
        MedicalRecordAuditPrintPdfView.as_view(),
        name="medical_record_audit_print_pdf",
    ),
    # Báo cáo sự cố y khoa
    path(
        "incidents/",
        IncidentReportListView.as_view(),
        name="incident_report_list",
    ),
    path(
        "incidents/new/",
        IncidentReportCreateView.as_view(),
        name="incident_report_create",
    ),
    path(
        "incidents/<int:pk>/edit/",
        IncidentReportUpdateView.as_view(),
        name="incident_report_update",
    ),
    path(
        "incidents/<int:pk>/print/",
        IncidentReportPrintPdfView.as_view(),
        name="incident_report_print_pdf",
    ),
    path(
        "incident-report/",
         IncidentReportPublicCreateView.as_view(),
         name="incident_report_public"
    ),
path("incident-report/thanks/", IncidentReportThanksView.as_view(), name="incident_report_thanks"),
]
