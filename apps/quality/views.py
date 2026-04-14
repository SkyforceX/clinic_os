# apps/quality/views.py
import os
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.db.models import Q
from django.utils.dateparse import parse_date
from datetime import date

from docxtpl import DocxTemplate

from .models import MedicalRecordAudit, IncidentReport, IncidentAttachment
from .forms import MedicalRecordAuditForm, IncidentReportForm
from .utils import (
    build_medical_record_audit_context,
    build_incident_report_context,
    convert_docx_to_pdf_with_libreoffice
)

def _parse_any_date(value: str):
    """
    Hỗ trợ cả 'yyyy-mm-dd' (input type=date) và 'dd/mm/yyyy'.
    Trả về datetime.date hoặc None.
    """
    if not value:
        return None
    value = value.strip()
    # Thử chuẩn ISO yyyy-mm-dd trước
    d = parse_date(value)
    if d:
        return d
    # Thử dd/mm/yyyy
    try:
        day, month, year = value.split("/")
        return date(int(year), int(month), int(day))
    except Exception:
        return None

class MedicalRecordAuditListView(LoginRequiredMixin, ListView):
    model = MedicalRecordAudit
    template_name = "quality/medical_record_audit_list.html"
    context_object_name = "audits"

    def get_queryset(self):
        qs = (
            MedicalRecordAudit.objects
            .filter(created_by=self.request.user)
            .order_by("-created_at")
        )

        q = self.request.GET.get("q", "").strip()
        from_str = self.request.GET.get("from", "").strip()
        to_str = self.request.GET.get("to", "").strip()

        # Lọc theo tên BN / mã BN
        if q:
            qs = qs.filter(
                Q(patient_name__icontains=q) |
                Q(patient_code__icontains=q)
            )

        date_field = "visit_date"
        date_from = _parse_any_date(from_str)
        date_to = _parse_any_date(to_str)

        if date_from:
            qs = qs.filter(**{f"{date_field}__gte": date_from})
        if date_to:
            qs = qs.filter(**{f"{date_field}__lte": date_to})

        return qs


class MedicalRecordAuditCreateView(LoginRequiredMixin, CreateView):
    model = MedicalRecordAudit
    form_class = MedicalRecordAuditForm
    template_name = "quality/medical_record_audit_form.html"
    success_url = reverse_lazy("quality:medical_record_audit_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Đã tạo phiếu đánh giá hồ sơ thành công.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Không thể lưu phiếu đánh giá. Vui lòng kiểm tra lại.")
        return super().form_invalid(form)


class MedicalRecordAuditUpdateView(LoginRequiredMixin, UpdateView):
    model = MedicalRecordAudit
    form_class = MedicalRecordAuditForm
    template_name = "quality/medical_record_audit_form.html"
    success_url = reverse_lazy("quality:medical_record_audit_list")

    def get_queryset(self):
        # Chỉ cho phép sửa hồ sơ do chính user đó tạo
        return MedicalRecordAudit.objects.filter(created_by=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Đã cập nhật phiếu đánh giá thành công.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Có lỗi xảy ra khi cập nhật. Kiểm tra lại thông tin nhập.")
        return super().form_invalid(form)


class MedicalRecordAuditPrintPdfView(LoginRequiredMixin, View):
    TEMPLATE_SETTING_NAME = "QUALITY_AUDIT_TEMPLATE"

    def get_template_path(self) -> Path:
        template_path = getattr(settings, self.TEMPLATE_SETTING_NAME, None)
        if not template_path:
            template_path = Path(settings.BASE_DIR) / "templates" / "word" / "medical_record_audit_template.docx"
        else:
            template_path = Path(template_path)

        if not template_path.exists():
            raise Http404(f"Mẫu Word không tồn tại: {template_path}")
        return template_path

    def get(self, request, pk):
        audit = get_object_or_404(
            MedicalRecordAudit,
            pk=pk,
            created_by=request.user,
        )

        template_path = self.get_template_path()
        context = build_medical_record_audit_context(audit)

        base_tmp_dir = Path(getattr(settings, "QUALITY_DOCX_TMP_DIR", settings.BASE_DIR / "tmp_docs"))
        base_tmp_dir.mkdir(exist_ok=True)

        docx_out = base_tmp_dir / f"audit_{audit.pk}.docx"
        pdf_out = base_tmp_dir / f"audit_{audit.pk}.pdf"

        # 1. Render DOCX
        print(">>> TEMPLATE_PATH:", template_path, "exists?", template_path.exists())
        print(">>> TMP_DIR:", base_tmp_dir)

        tpl = DocxTemplate(str(template_path))
        tpl.render(context)
        tpl.save(str(docx_out))

        print(">>> DOCX_OUT:", docx_out, "exists?", docx_out.exists())
        if not docx_out.exists():
            raise RuntimeError(f"File DOCX tạm chưa được tạo: {docx_out}")

        # 2. Convert DOCX -> PDF bằng LibreOffice
        convert_docx_to_pdf_with_libreoffice(str(docx_out), str(pdf_out))

        print(">>> PDF_OUT:", pdf_out, "exists?", pdf_out.exists())
        if not pdf_out.exists():
            raise RuntimeError("LibreOffice đã chạy nhưng không tạo được file PDF.")

        pdf_data = pdf_out.read_bytes()
        resp = HttpResponse(pdf_data, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename=\"audit_{audit.pk}.pdf\"'
        return resp

class IncidentReportListView(LoginRequiredMixin, ListView):
    model = IncidentReport
    template_name = "quality/incident_report_list.html"
    context_object_name = "reports"

    def get_queryset(self):
        qs = (
            IncidentReport.objects
            .order_by("-incident_datetime", "-created_at")
        )

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(incident_name__icontains=q)
                | Q(patient_name__icontains=q)
                | Q(patient_code__icontains=q)
                | Q(department__icontains=q)
            )
        return qs


from django.contrib.auth import get_user_model
User = get_user_model()

def get_anonymous_user():
    """
    Trả về user dùng cho báo cáo public.
    Cách 1: lấy từ settings.QUALITY_ANON_USERNAME
    Cách 2: fallback tạo / get user 'anonymous.incident'
    """
    username = getattr(settings, "QUALITY_ANON_USERNAME", "anonymous.incident")
    user, _ = User.objects.get_or_create(username=username, defaults={"is_active": True})
    return user


class IncidentAttachmentSaveMixin:
    """
    Dùng chung cho public + staff: lưu tất cả file trong request.FILES['attachments'].
    """
    def _save_attachments(self):
        files = self.request.FILES.getlist("attachments")
        for f in files:
            IncidentAttachment.objects.create(incident=self.object, image=f)

    def form_valid(self, form):
        response = super().form_valid(form)  # self.object đã có pk
        self._save_attachments()
        return response

from django.urls import reverse_lazy
class IncidentReportPublicCreateView(IncidentAttachmentSaveMixin, CreateView):
    model = IncidentReport
    form_class = IncidentReportForm
    template_name = "quality/incident_report_public_form.html"
    success_url = reverse_lazy("quality:incident_report_thanks")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = None
        return kwargs

    def form_valid(self, form):
        form.instance.reported_by = get_anonymous_user()
        messages.success(self.request, "Đã gửi báo cáo sự cố. Cảm ơn anh/chị.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Không thể gửi báo cáo, vui lòng kiểm tra lại các thông tin bắt buộc.")
        return super().form_invalid(form)


class IncidentReportThanksView(TemplateView):
    template_name = "quality/incident_report_thanks.html"


class IncidentReportCreateView(LoginRequiredMixin, IncidentAttachmentSaveMixin, CreateView):
    model = IncidentReport
    form_class = IncidentReportForm
    template_name = "quality/incident_report_form.html"
    success_url = reverse_lazy("quality:incident_report_thanks")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        messages.success(self.request, "Đã tạo báo cáo sự cố thành công.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, str(form.non_field_errors()) or "Có lỗi xảy ra, không thể lưu báo cáo.")
        return super().form_invalid(form)


class IncidentReportUpdateView(LoginRequiredMixin, IncidentAttachmentSaveMixin, UpdateView):
    model = IncidentReport
    form_class = IncidentReportForm
    template_name = "quality/incident_report_form.html"
    success_url = reverse_lazy("quality:incident_report_list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.reported_by_id != request.user.id:
            messages.error(request, "Bạn không có quyền sửa báo cáo của người khác.")
            return redirect("quality:incident_report_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Đã cập nhật báo cáo sự cố.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Có lỗi xảy ra, không thể cập nhật.")
        return super().form_invalid(form)


class IncidentReportPrintPdfView(LoginRequiredMixin, View):
    TEMPLATE_SETTING_NAME = "QUALITY_INCIDENT_TEMPLATE"

    def get_template_path(self) -> Path:
        """
        Lấy đường dẫn file .docx dùng làm mẫu in báo cáo sự cố.
        - Nếu trong settings có QUALITY_INCIDENT_TEMPLATE thì dùng
        - Ngược lại dùng templates/word/incident_report_template.docx
        """
        template_path = getattr(settings, self.TEMPLATE_SETTING_NAME, None)
        if not template_path:
            template_path = Path(settings.BASE_DIR) / "templates" / "word" / "incident_report_template.docx"
        else:
            template_path = Path(template_path)

        if not template_path.exists():
            raise Http404(f"Mẫu Word không tồn tại: {template_path}")
        return template_path

    def get(self, request, pk):
        incident = get_object_or_404(
            IncidentReport,
            pk=pk,
            #reported_by=request.user,  # chỉ in báo cáo của chính mình
        )

        template_path = self.get_template_path()
        context = build_incident_report_context(incident)

        base_tmp_dir = Path(getattr(settings, "QUALITY_DOCX_TMP_DIR", settings.BASE_DIR / "tmp_docs"))
        base_tmp_dir.mkdir(exist_ok=True)

        docx_out = base_tmp_dir / f"incident_{incident.pk}.docx"
        pdf_out = base_tmp_dir / f"incident_{incident.pk}.pdf"

        # 1. Render DOCX
        print(">>> TEMPLATE_PATH:", template_path, "exists?", template_path.exists())
        print(">>> TMP_DIR:", base_tmp_dir)

        tpl = DocxTemplate(str(template_path))
        tpl.render(context)
        tpl.save(str(docx_out))

        print(">>> DOCX_OUT:", docx_out, "exists?", docx_out.exists())
        if not docx_out.exists():
            raise RuntimeError(f"File DOCX tạm chưa được tạo: {docx_out}")

        # 2. Convert DOCX -> PDF bằng LibreOffice
        convert_docx_to_pdf_with_libreoffice(str(docx_out), str(pdf_out))

        print(">>> PDF_OUT:", pdf_out, "exists?", pdf_out.exists())
        if not pdf_out.exists():
            raise RuntimeError("LibreOffice đã chạy nhưng không tạo được file PDF.")

        pdf_data = pdf_out.read_bytes()
        resp = HttpResponse(pdf_data, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="incident_{incident.pk}.pdf"'
        return resp
