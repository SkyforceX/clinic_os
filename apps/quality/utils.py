import os
import subprocess
from django.conf import settings

from .models import MedicalRecordAudit, AuditChoice, IncidentReport


def display_audit_choice(val: str) -> str:
    mapping = {
        AuditChoice.PASS_: "Đạt",
        AuditChoice.FAIL_: "Không đạt",
        AuditChoice.NA: "Không áp dụng",
        None: "",
        "": "",
    }
    return mapping.get(val, str(val))


def build_medical_record_audit_context(audit: MedicalRecordAudit) -> dict:
    score_percent = getattr(audit, "score_percent", None)

    ctx = {
        "patient_name": audit.patient_name,
        "patient_code": audit.patient_code or "",
        "visit_date": audit.visit_date.strftime("%d/%m/%Y") if audit.visit_date else "",
        "doctor_name": audit.doctor_name or "",
        "clinic_room": audit.clinic_room or "",
        "score_percent": score_percent if score_percent is not None else "",
        "overall_comment": audit.overall_comment or "",
    }

    field_names = MedicalRecordAudit.get_audit_field_names()
    for name in field_names:
        ctx[name] = display_audit_choice(getattr(audit, name))

    return ctx


def build_incident_report_context(incident: IncidentReport) -> dict:
    """
    Chuẩn dữ liệu để merge vào template báo cáo sự cố ISO.
    """
    user = incident.reported_by
    if hasattr(user, "get_full_name"):
        reporter_name = user.get_full_name() or user.username
    else:
        reporter_name = getattr(user, "username", "") or str(user)

    # ===== Severity =====
    severity_display = (
        incident.get_severity_display() if incident.severity else ""
    )
    severity_raw = incident.severity or ""

    # ===== Incident Type =====
    incident_type_display = (
        incident.get_incident_type_display()
        if hasattr(incident, "get_incident_type_display") and incident.incident_type
        else ""
    )
    incident_type_raw = incident.incident_type or ""

    # ===== Related Policy =====
    related_policy_display = (
        incident.get_related_policy_display()
        if hasattr(incident, "get_related_policy_display") and incident.related_policy
        else incident.related_policy or ""
    )
    related_policy_raw = incident.related_policy or ""

    # ===== Incident Name =====
    incident_name_display = (
        incident.get_incident_name_display()
        if hasattr(incident, "get_incident_name_display") and incident.incident_name
        else incident.incident_name or ""
    )
    incident_name_raw = incident.incident_name or ""

    # ===== Attachments =====
    attachments = incident.attachments.all()
    attachments_inline = ", ".join(
        [a.image.name for a in attachments]
    ) if attachments else ""

    # Nếu muốn xuống dòng mỗi file:
    # attachments_inline = "\n".join([a.image.name for a in attachments])

    ctx = {
        # ===== 1. Thông tin chung =====
        "department": "",  # bạn sẽ thêm trường department sau
        "reporter_name": reporter_name,
        "is_anonymous_to_department": "Có" if incident.is_anonymous_to_department else "Không",
        "patient_name": incident.patient_name or "",
        "patient_code": incident.patient_code or "",
        "incident_type_display": incident_type_display,
        "incident_type": incident_type_raw,
        "incident_datetime": (
            incident.incident_datetime.strftime("%d/%m/%Y %H:%M")
            if incident.incident_datetime else ""
        ),
        "location": incident.location or "",
        "severity_display": severity_display,
        "severity": severity_raw,

        # ===== 2. Quy trình - chính sách =====
        "related_policy_display": related_policy_display,
        "related_policy": related_policy_raw,
        "incident_name_display": incident_name_display,
        "incident_name": incident_name_raw,

        # ===== 3. Diễn biến & hậu quả =====
        "description": incident.description or "",
        "consequence": incident.consequence or "",

        # ===== 4. Hành động khắc phục =====
        "immediate_action": incident.immediate_action or "",
        "followup_action_quality": incident.followup_action_quality or "",
        "followup_action_department": incident.followup_action_department or "",
        "training_plan": incident.training_plan or "",
        "other_corrective_actions": incident.other_corrective_actions or "",

        # ===== 5. Đính kèm =====
        "attachment_note": incident.attachment_note or "",
        "attachments_inline": attachments_inline,

        # ===== 6. Metadata =====
        "created_date": incident.created_at.strftime("%d/%m/%Y"),
    }

    return ctx


def convert_docx_to_pdf_with_libreoffice(docx_path: str, pdf_path: str):
    """
    Convert .docx -> .pdf bằng LibreOffice headless.
    Phù hợp chạy trong service (uvicorn + IIS reverse proxy).
    """
    docx_path = os.path.abspath(str(docx_path))
    pdf_path = os.path.abspath(str(pdf_path))

    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"Không tìm thấy file DOCX: {docx_path}")

    outdir = os.path.dirname(pdf_path)

    soffice_path = getattr(settings, "LIBREOFFICE_PATH", "soffice")

    cmd = [
        soffice_path,
        "--headless",
        "--nologo",
        "--convert-to",
        "pdf",
        "--outdir",
        outdir,
        docx_path,
    ]

    print(">>> RUN:", " ".join(cmd))

    # Nếu LibreOffice lỗi sẽ raise CalledProcessError
    subprocess.run(cmd, condition=True)

    # Một số bản LibreOffice có thể đặt tên file hơi khác, nên chuẩn hoá lại
    if not os.path.exists(pdf_path):
        base = os.path.splitext(os.path.basename(docx_path))[0]
        for fname in os.listdir(outdir):
            if fname.lower() == f"{base}.pdf":
                real_pdf = os.path.join(outdir, fname)
                os.replace(real_pdf, pdf_path)
                break

    if not os.path.exists(pdf_path):
        raise RuntimeError(f"LibreOffice đã chạy nhưng không tạo được PDF cho {docx_path}")
