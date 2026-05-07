import csv
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import date
from functools import reduce
from operator import or_
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView

from apps.his_integration.models import (
    HisSyncJob,
    HisCorporatePackageSync,
    HisExamRecordSync,
    HisPatientSync,
    HisPatientTypeSync,
    HisDiagnosticImagingSync,
    HisDiagnosticImagingItemSync,
    HisFunctionalTestSync,
    HisFunctionalTestItemSync,
    HisExamServiceItemSync,
    HisAppointmentSync,
    HisServiceCatalogSync,
    HisPackageServiceSync,
    HisInvoiceSync,
    HisInvoiceDetailSync,
)
from apps.his_integration.selectors import (
    corporate_package_detail_queryset,
    exam_record_detail_queryset,
    get_his_sync_dashboard_stats,
    get_his_sync_job_watchlist,
    get_his_sync_quality_warnings,
    get_package_exam_record_stats,
    list_active_corporate_packages,
    list_active_corporate_packages_for_sale_user,
    list_active_exam_records,
    list_active_packages_for_filter,
    list_contracts_available_for_his_package_link,
    list_exam_records_for_package,
    list_recent_sync_jobs,
    list_schedule_configs_available_for_his_package_link,
    list_sync_jobs,
)
from apps.his_integration.services import (
    HisPackageLinkingError,
    SOURCE_HIS_MSSQL,
    SOURCE_LOCAL_PG,
    InvalidHisSyncType,
    dispatch_his_sync,
    link_contract_to_his_package,
    link_schedule_config_to_his_package,
    unlink_schedule_config_from_his_package,
)


logger = logging.getLogger(__name__)


def _strip_accents(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_service_key(name: str) -> str:
    text = _strip_accents(name).lower().strip()
    text = re.sub(r"\s*[-/]\s*(nam|nu|nữ)\s*$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _display_service_name(name: str) -> str:
    text = str(name or "").strip()
    text = re.sub(r"\s*[-/]\s*(Nam|Nữ|Nu)\s*$", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _is_ultrasound_catalog(service_catalog) -> bool:
    if not service_catalog:
        return False

    haystacks = [
        getattr(service_catalog, "service_item_name", ""),
        getattr(service_catalog, "service_item_name_order", ""),
        getattr(service_catalog, "service_group_code", ""),
        getattr(service_catalog, "service_sub_group_code", ""),
        getattr(service_catalog, "report_group_code", ""),
        getattr(service_catalog, "common_group_code", ""),
    ]
    normalized = " | ".join(_strip_accents(value).lower() for value in haystacks if value)
    if not normalized:
        return False

    if any(keyword in normalized for keyword in ("sieu am", "sieuam", "ultrasound")):
        return True

    code_tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", normalized)
        if token
    }
    return "sa" in code_tokens and ("cdha" in code_tokens or "cls" in code_tokens)


_QUALITY_WARNING_TARGETS = {
    "exam_records_missing_patient": ("his_integration:exam_record_list", {"quality_warning": "exam_records_missing_patient"}),
    "exam_records_missing_package": ("his_integration:exam_record_list", {"quality_warning": "exam_records_missing_package"}),
    "package_services_missing_package": ("his_integration:data_list", {"entity_type": "package_services", "quality_warning": "package_services_missing_package"}),
    "package_services_missing_service": ("his_integration:data_list", {"entity_type": "package_services", "quality_warning": "package_services_missing_service"}),
    "exam_service_items_missing_record": ("his_integration:data_list", {"entity_type": "exam_service_items", "quality_warning": "exam_service_items_missing_record"}),
    "exam_service_items_missing_service": ("his_integration:data_list", {"entity_type": "exam_service_items", "quality_warning": "exam_service_items_missing_service"}),
    "diagnostic_imaging_missing_record": ("his_integration:data_list", {"entity_type": "diagnostic_imaging", "quality_warning": "diagnostic_imaging_missing_record"}),
    "functional_tests_missing_record": ("his_integration:data_list", {"entity_type": "functional_tests", "quality_warning": "functional_tests_missing_record"}),
}


def _quality_warning_url(warning_key: str) -> str:
    target = _QUALITY_WARNING_TARGETS.get(warning_key)
    if not target:
        return ""

    route_name, params = target
    path_kwargs = {}
    query_params = {}
    for key, value in params.items():
        if key == "entity_type":
            path_kwargs[key] = value
        else:
            query_params[key] = value

    url = reverse(route_name, kwargs=path_kwargs)
    if query_params:
        return f"{url}?{urlencode(query_params)}"
    return url


def _get_quality_warning_detail_rows(warning_key: str, *, sample_limit: int | None = None) -> list[dict]:
    if warning_key == "exam_records_missing_patient":
        qs = (
            HisExamRecordSync.objects.filter(is_active=True, patient_sync__isnull=True)
            .order_by("-last_synced_at")
        )
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "ExamRecord",
                "primary": row.his_record_code,
                "secondary": (row.raw_payload or {}).get("MaBenhNhan") or "",
                "detail": "Missing patient link",
                "link": reverse("his_integration:exam_record_detail", kwargs={"pk": row.pk}),
            }
            for row in qs
        ]

    if warning_key == "exam_records_missing_package":
        qs = (
            HisExamRecordSync.objects.filter(is_active=True, package_sync__isnull=True)
            .exclude(raw_payload__MaGoiKhamTheoDoan__in=["", None])
            .order_by("-last_synced_at")
        )
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "ExamRecord",
                "primary": row.his_record_code,
                "secondary": (row.raw_payload or {}).get("MaGoiKhamTheoDoan") or "",
                "detail": "Missing package link",
                "link": reverse("his_integration:exam_record_detail", kwargs={"pk": row.pk}),
            }
            for row in qs
        ]

    if warning_key == "package_services_missing_package":
        qs = (
            HisPackageServiceSync.objects.filter(is_active=True, package_sync__isnull=True)
            .exclude(his_package_code__in=["", None])
            .order_by("-last_synced_at")
        )
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "PackageService",
                "primary": row.his_order_code,
                "secondary": row.his_package_code,
                "detail": "Missing package link",
                "link": _quality_warning_url(warning_key),
            }
            for row in qs
        ]

    if warning_key == "package_services_missing_service":
        qs = (
            HisPackageServiceSync.objects.filter(is_active=True, service_catalog__isnull=True)
            .exclude(service_item_code__in=["", None])
            .order_by("-last_synced_at")
        )
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "PackageService",
                "primary": row.his_order_code,
                "secondary": row.service_item_code,
                "detail": "Missing service catalog link",
                "link": _quality_warning_url(warning_key),
            }
            for row in qs
        ]

    if warning_key == "exam_service_items_missing_record":
        qs = HisExamServiceItemSync.objects.filter(is_active=True, exam_record_sync__isnull=True).order_by("-last_synced_at")
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "ExamServiceItem",
                "primary": row.ma_kham_benh,
                "secondary": row.service_item_code,
                "detail": "Missing exam record link",
                "link": _quality_warning_url(warning_key),
            }
            for row in qs
        ]

    if warning_key == "exam_service_items_missing_service":
        qs = (
            HisExamServiceItemSync.objects.filter(is_active=True, service_catalog__isnull=True)
            .exclude(service_item_code__in=["", None])
            .order_by("-last_synced_at")
        )
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "ExamServiceItem",
                "primary": row.ma_kham_benh,
                "secondary": row.service_item_code,
                "detail": "Missing service catalog link",
                "link": _quality_warning_url(warning_key),
            }
            for row in qs
        ]

    if warning_key == "diagnostic_imaging_missing_record":
        qs = HisDiagnosticImagingSync.objects.filter(is_active=True, exam_record_sync__isnull=True).order_by("-last_synced_at")
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "DiagnosticImaging",
                "primary": row.his_imaging_code,
                "secondary": (row.raw_payload or {}).get("MaHoSo") or "",
                "detail": "Missing exam record link",
                "link": _quality_warning_url(warning_key),
            }
            for row in qs
        ]

    if warning_key == "functional_tests_missing_record":
        qs = HisFunctionalTestSync.objects.filter(is_active=True, exam_record_sync__isnull=True).order_by("-last_synced_at")
        if sample_limit:
            qs = qs[:sample_limit]
        return [
            {
                "group": "FunctionalTest",
                "primary": row.his_ft_code,
                "secondary": (row.raw_payload or {}).get("MaHoSo") or "",
                "detail": "Missing exam record link",
                "link": _quality_warning_url(warning_key),
            }
            for row in qs
        ]

    return []


# ─── Helpers dùng cho data_list ────────────────────────────────────────────

def _fmt_dt(dt):
    return dt.strftime('%d/%m/%Y %H:%M') if dt else ''


def _fmt_date(d):
    return d.strftime('%d/%m/%Y') if d else ''


def _yn(v):
    if v is None:
        return ''
    return 'Có' if v else 'Không'


def _trunc(s, n=100):
    if not s:
        return ''
    s = str(s)
    return s[:n] + '…' if len(s) > n else s


def _fmt_money(v):
    if v is None:
        return ''
    try:
        return f"{int(round(float(v))):,}"
    except (TypeError, ValueError):
        return ''


_ENTITY_CONFIGS = {
    'patients': {
        'title': 'Danh sách Bệnh nhân HIS',
        'queryset_fn': lambda: HisPatientSync.objects.filter(is_active=True).order_by('full_name'),
        'search_fields': ['full_name', 'his_patient_code', 'phone', 'national_id'],
        'columns': ['Mã BN HIS', 'Họ tên', 'Ngày sinh', 'Giới tính', 'SĐT', 'Email', 'CMND/CCCD', 'Địa chỉ', 'VIP', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_patient_code, o.full_name, o.birth_date_display,
            o.gioi_tinh, o.phone, o.email, o.national_id,
            _trunc(o.address), _yn(o.vip_flag), _fmt_dt(o.last_synced_at),
        ],
    },
    'patient_types': {
        'title': 'Đối tượng Bệnh nhân HIS',
        'queryset_fn': lambda: HisPatientTypeSync.objects.filter(is_active=True).order_by('patient_type_name'),
        'search_fields': ['his_patient_type_code', 'patient_type_name'],
        'columns': ['Mã đối tượng', 'Tên đối tượng', 'Mô tả', 'Có thẻ', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_patient_type_code, o.patient_type_name,
            _trunc(o.description, 80), _yn(o.has_card), _fmt_dt(o.last_synced_at),
        ],
    },
    'diagnostic_imaging': {
        'title': 'Chẩn đoán Hình ảnh HIS',
        'queryset_fn': lambda: (
            HisDiagnosticImagingSync.objects.filter(is_active=True)
            .select_related('patient_sync')
            .order_by('-exam_date')
        ),
        'search_fields': ['his_imaging_code', 'patient_sync__his_patient_code', 'patient_sync__full_name', 'service_code'],
        'columns': ['Mã CĐHA HIS', 'Bệnh nhân', 'Mã BN', 'Ngày vào khám', 'Mã dịch vụ', 'Mã BS CĐHA', 'Mã BS TH', 'Kết luận', 'TT phiếu', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_imaging_code,
            o.patient_sync.full_name if o.patient_sync else '',
            o.patient_sync.his_patient_code if o.patient_sync else '',
            _fmt_dt(o.exam_date), o.service_code,
            o.imaging_doctor_code, o.performing_doctor_code,
            _trunc(o.conclusion), '' if o.status_code is None else o.status_code,
            _fmt_dt(o.last_synced_at),
        ],
    },
    'functional_tests': {
        'title': 'Phiếu Thăm dò Chức năng HIS',
        'queryset_fn': lambda: (
            HisFunctionalTestSync.objects.filter(is_active=True)
            .select_related('patient_sync')
            .order_by('-exam_date')
        ),
        'search_fields': ['his_ft_code', 'patient_sync__his_patient_code', 'patient_sync__full_name', 'service_code'],
        'columns': ['Mã TDCN HIS', 'Bệnh nhân', 'Mã BN', 'Ngày vào khám', 'Mã dịch vụ', 'Mã BS TDCN', 'Mã BS TH', 'Kết luận', 'TT phiếu', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_ft_code,
            o.patient_sync.full_name if o.patient_sync else '',
            o.patient_sync.his_patient_code if o.patient_sync else '',
            _fmt_dt(o.exam_date), o.service_code,
            o.ft_doctor_code, o.performing_doctor_code,
            _trunc(o.conclusion), '' if o.status_code is None else o.status_code,
            _fmt_dt(o.last_synced_at),
        ],
    },
    'exam_service_items': {
        'title': 'Chi tiết Dịch vụ Khám HIS',
        'queryset_fn': lambda: (
            HisExamServiceItemSync.objects.filter(is_active=True)
            .select_related('exam_record_sync')
            .order_by('-last_synced_at')
        ),
        'search_fields': ['ma_kham_benh', 'service_item_code', 'exam_record_sync__his_record_code'],
        'columns': ['Mã phiếu KB', 'Mã hồ sơ HIS', 'Mã chỉ tiêu', 'Đơn giá', 'Số lượng', 'Đã thu tiền', 'Trọn gói', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.ma_kham_benh,
            o.exam_record_sync.his_record_code if o.exam_record_sync else '',
            o.service_item_code, _fmt_money(o.unit_price),
            '' if o.quantity is None else o.quantity,
            _fmt_money(o.collected_amount), _yn(o.is_package_service),
            _fmt_dt(o.last_synced_at),
        ],
    },
    'appointments': {
        'title': 'Danh sách Lịch hẹn HIS',
        'queryset_fn': lambda: HisAppointmentSync.objects.filter(is_active=True).order_by('-start_datetime'),
        'search_fields': ['patient_name', 'his_patient_code', 'his_record_code', 'booking_code'],
        'columns': ['ID lịch hẹn', 'Tên BN', 'Mã BN HIS', 'Mã hồ sơ HIS', 'Mã BS', 'Mã khoa', 'Nội dung hẹn', 'Ngày bắt đầu', 'Ngày kết thúc', 'Trạng thái', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_appointment_id, o.patient_name, o.his_patient_code,
            o.his_record_code, o.doctor_code, o.department_code,
            _trunc(o.content, 60), _fmt_dt(o.start_datetime),
            _fmt_dt(o.end_datetime), o.status, _fmt_dt(o.last_synced_at),
        ],
    },
    'service_catalog': {
        'title': 'Danh mục Dịch vụ HIS',
        'queryset_fn': lambda: HisServiceCatalogSync.objects.filter(is_active=True).order_by('service_item_code'),
        'search_fields': ['service_item_code', 'service_item_name', 'service_group_code'],
        'columns': ['Mã chỉ tiêu', 'Tên chỉ tiêu', 'Mã nhóm DV', 'Đơn vị', 'Trị số BT', 'Kỹ thuật cao', 'Đang dùng', 'Hiển thị', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.service_item_code, o.service_item_name, o.service_group_code,
            o.unit, _trunc(o.normal_value, 50),
            _yn(o.is_high_tech), _yn(o.is_active_use), _yn(o.is_visible),
            _fmt_dt(o.last_synced_at),
        ],
    },
    'package_services': {
        'title': 'Dịch vụ theo Gói đoàn HIS',
        'queryset_fn': lambda: (
            HisPackageServiceSync.objects.filter(is_active=True)
            .select_related('package_sync')
            .order_by('his_order_code')
        ),
        'search_fields': ['his_order_code', 'service_item_code', 'package_sync__his_package_code', 'package_sync__package_name'],
        'columns': ['Mã đơn', 'Mã gói HIS', 'Tên gói khám', 'Mã chỉ tiêu', 'Đơn vị', 'Số lượng', 'Đơn giá', 'Thành tiền', 'Ngoài gói', 'Được chọn', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_order_code,
            o.package_sync.his_package_code if o.package_sync else '',
            _trunc(o.package_sync.package_name, 50) if o.package_sync else '',
            o.service_item_code, o.unit, o.quantity,
            _fmt_money(o.unit_price), _fmt_money(o.total_amount),
            _yn(o.is_outside_package), _yn(o.is_selected),
            _fmt_dt(o.last_synced_at),
        ],
    },
    'invoices': {
        'title': 'Danh sách Hóa đơn HIS',
        'queryset_fn': lambda: HisInvoiceSync.objects.filter(is_active=True).order_by('-invoice_date', '-created_date'),
        'search_fields': ['his_invoice_ref_id', 'his_patient_code', 'customer_name', 'inv_no'],
        'columns': ['RefID HIS', 'Mã BN HIS', 'Tên khách hàng', 'Ngày HĐ', 'Số HĐ', 'Ký hiệu', 'Tổng tiền', 'Tổng CK', 'Tổng VAT', 'Trạng thái PH', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_invoice_ref_id, o.his_patient_code,
            _trunc(o.customer_name, 60), _fmt_date(o.invoice_date),
            o.inv_no, o.inv_series,
            _fmt_money(o.total_sale_amount), _fmt_money(o.total_discount_amount),
            _fmt_money(o.total_vat_amount), o.get_publish_status_display(),
            _fmt_dt(o.last_synced_at),
        ],
    },
    'invoice_details': {
        'title': 'Chi tiết Hóa đơn HIS',
        'queryset_fn': lambda: (
            HisInvoiceDetailSync.objects.filter(is_active=True)
            .select_related('invoice_sync')
            .order_by('invoice_sync_id', 'sort_order')
        ),
        'search_fields': ['his_ref_detail_id', 'inventory_item_code', 'description', 'invoice_sync__his_invoice_ref_id'],
        'columns': ['RefDetailID HIS', 'Mã HĐ', 'Mã vật tư/DV', 'Diễn giải', 'ĐVT', 'Số lượng', 'Đơn giá', 'Thành tiền', '% CK', 'Tiền CK', '% VAT', 'Tiền VAT', 'Đồng bộ cuối'],
        'row_fn': lambda o: [
            o.his_ref_detail_id,
            o.invoice_sync.his_invoice_ref_id if o.invoice_sync else '',
            o.inventory_item_code, _trunc(o.description, 80),
            o.unit_name, o.quantity,
            _fmt_money(o.unit_price), _fmt_money(o.amount),
            o.discount_rate, _fmt_money(o.discount_amount),
            o.vat_rate, _fmt_money(o.vat_amount),
            _fmt_dt(o.last_synced_at),
        ],
    },
}


def _is_local_sync_enabled() -> bool:
    return bool(settings.DEBUG or settings.HIS_LOCAL_SYNC_ENABLED)


def _classify_sync_exception(exc: Exception) -> tuple[str, str]:
    message = str(exc).strip() or exc.__class__.__name__
    exc_name = exc.__class__.__name__.lower()
    exc_module = exc.__class__.__module__.lower()
    normalized = f"{exc_module}.{exc_name} {message.lower()}"

    if any(token in normalized for token in ("redis", "kombu", "amqp", "broker")):
        return "redis_celery", f"Lỗi Redis/Celery broker: {message}"

    if any(token in normalized for token in ("pyodbc", "sql server", "odbc driver", "his mssql", "hissourceerror")):
        return "his_mssql", f"Lỗi kết nối HIS MSSQL: {message}"

    if any(token in normalized for token in ("connection refused", "timed out", "timeout", "network")):
        return "network", f"Lỗi mạng/kết nối: {message}"

    return "unexpected", message


def _is_operations(user) -> bool:
    return user.groups.filter(name__in=[
        "Operations Team", "Operations", "VH", "Vận hành", "Van hanh",
    ]).exists()


def _is_sales(user) -> bool:
    return user.groups.filter(name__in=["Sales Team", "Sales"]).exists()


def _is_executive(user) -> bool:
    return (not getattr(user, "is_superuser", False)) and user.groups.filter(
        name__in=["Executive", "Executives"]
    ).exists()


def _is_it_admin(user) -> bool:
    return getattr(user, "is_superuser", False) or user.groups.filter(
        name__in=["IT Admin", "IT", "IT Support"]
    ).exists()


def _package_list_role_flags(user) -> dict:
    is_su = getattr(user, "is_superuser", False)
    ops = _is_operations(user)
    sales = _is_sales(user)
    exec_ = _is_executive(user)
    it = _is_it_admin(user)
    return {
        "show_all_packages": is_su or ops or exec_ or it,
        "can_link_contract": not ops,       # Operations Team không link HĐ
        "can_link_schedule": not sales,     # Sales không link lịch khám
        "executive_view_only": exec_,       # Executive: thấy nút nhưng không lưu
        "is_sales_user": sales,
        "is_superuser": is_su,
        "can_unlink_schedule": is_su or (it and not exec_),  # Superuser + IT Staff gỡ lịch
    }


class HisDataListView(LoginRequiredMixin, ListView):
    template_name = 'his_integration/staff/data_list.html'
    context_object_name = 'object_list'
    paginate_by = 50

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.entity_type = kwargs.get('entity_type', '')
        if self.entity_type not in _ENTITY_CONFIGS:
            raise Http404

    def get_queryset(self):
        config = _ENTITY_CONFIGS[self.entity_type]
        qs = config['queryset_fn']()
        q = self.request.GET.get('q', '').strip()
        quality_warning = self.request.GET.get('quality_warning', '').strip()

        if self.entity_type == 'package_services':
            if quality_warning == 'package_services_missing_package':
                qs = qs.filter(is_active=True, package_sync__isnull=True).exclude(his_package_code__in=['', None])
            elif quality_warning == 'package_services_missing_service':
                qs = qs.filter(is_active=True, service_catalog__isnull=True).exclude(service_item_code__in=['', None])
        elif self.entity_type == 'exam_service_items':
            if quality_warning == 'exam_service_items_missing_record':
                qs = qs.filter(is_active=True, exam_record_sync__isnull=True)
            elif quality_warning == 'exam_service_items_missing_service':
                qs = qs.filter(is_active=True, service_catalog__isnull=True).exclude(service_item_code__in=['', None])
        elif self.entity_type == 'diagnostic_imaging':
            if quality_warning == 'diagnostic_imaging_missing_record':
                qs = qs.filter(is_active=True, exam_record_sync__isnull=True)
        elif self.entity_type == 'functional_tests':
            if quality_warning == 'functional_tests_missing_record':
                qs = qs.filter(is_active=True, exam_record_sync__isnull=True)

        if q and config.get('search_fields'):
            filter_q = reduce(or_, (Q(**{f + '__icontains': q}) for f in config['search_fields']))
            qs = qs.filter(filter_q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = _ENTITY_CONFIGS[self.entity_type]
        page_obj = context['page_obj']
        paginator = context['paginator']

        # Smart page range (window ±3, with first/last anchors and ellipsis)
        num = page_obj.number
        total = paginator.num_pages
        lo = max(1, num - 3)
        hi = min(total, num + 3)
        pages = list(range(lo, hi + 1))
        if lo > 1:
            pages = [1] + (['…'] if lo > 2 else []) + pages
        if hi < total:
            pages = pages + (['…'] if hi < total - 1 else []) + [total]

        # Preserve current GET params except 'page'
        qs_copy = self.request.GET.copy()
        qs_copy.pop('page', None)
        base_qs = qs_copy.urlencode()

        context.update({
            'title': config['title'],
            'columns': config['columns'],
            'rows': [config['row_fn'](obj) for obj in context['object_list']],
            'q': self.request.GET.get('q', '').strip(),
            'quality_warning': self.request.GET.get('quality_warning', '').strip(),
            'entity_type': self.entity_type,
            'has_search': bool(config.get('search_fields')),
            'page_range': pages,
            'base_qs': base_qs,
            'active_quality_warning': next(
                (warning for warning in get_his_sync_quality_warnings(sample_limit=1)
                 if warning['key'] == self.request.GET.get('quality_warning', '').strip()),
                None,
            ),
        })
        return context


class HisSyncDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'his_integration/staff/sync_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = get_his_sync_dashboard_stats()
        context['job_watchlist'] = get_his_sync_job_watchlist()
        quality_warnings = get_his_sync_quality_warnings(sample_limit=5)
        for warning in quality_warnings:
            warning['url'] = _quality_warning_url(warning['key'])
        context['quality_warnings'] = quality_warnings
        context['recent_jobs'] = list_recent_sync_jobs(limit=10)
        context['local_sync_enabled'] = _is_local_sync_enabled()
        return context


class HisSyncQualityView(LoginRequiredMixin, TemplateView):
    template_name = 'his_integration/staff/sync_quality.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        warnings = get_his_sync_quality_warnings(sample_limit=5)
        selected_key = self.request.GET.get('warning', '').strip()
        selected_warning = next((warning for warning in warnings if warning['key'] == selected_key), None)

        for warning in warnings:
            warning['url'] = f"{reverse('his_integration:quality')}?warning={warning['key']}"
            warning['list_url'] = _quality_warning_url(warning['key'])
            warning['export_url'] = f"{reverse('his_integration:quality_export')}?warning={warning['key']}"

        context['quality_warnings'] = warnings
        context['selected_warning'] = selected_warning
        context['selected_rows'] = _get_quality_warning_detail_rows(selected_key, sample_limit=200) if selected_warning else []
        return context


@login_required(login_url="authentication:staff_login")
def export_quality_warning_csv(request):
    warning_key = (request.GET.get('warning') or '').strip()
    warning = next(
        (item for item in get_his_sync_quality_warnings(sample_limit=1) if item['key'] == warning_key),
        None,
    )
    if not warning:
        raise Http404

    rows = _get_quality_warning_detail_rows(warning_key)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="his_quality_{warning_key}.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['group', 'primary', 'secondary', 'detail', 'link'])
    for row in rows:
        writer.writerow([
            row.get('group', ''),
            row.get('primary', ''),
            row.get('secondary', ''),
            row.get('detail', ''),
            row.get('link', ''),
        ])
    return response


class HisSyncJobListView(LoginRequiredMixin, ListView):
    model = HisSyncJob
    template_name = 'his_integration/staff/sync_job_list.html'
    context_object_name = 'jobs'
    paginate_by = 50
    ordering = ['-created_at']
    
    def get_queryset(self):
        return list_sync_jobs()


class HisSyncJobDetailView(LoginRequiredMixin, DetailView):
    model = HisSyncJob
    template_name = 'his_integration/staff/sync_job_detail.html'
    context_object_name = 'job'
    
    def get_queryset(self):
        return list_sync_jobs()


class CorporatePackageListView(LoginRequiredMixin, ListView):
    model = HisCorporatePackageSync
    template_name = 'his_integration/staff/package_list.html'
    context_object_name = 'packages'
    paginate_by = 50

    def get_queryset(self):
        user = self.request.user
        flags = _package_list_role_flags(user)
        if flags["show_all_packages"]:
            return list_active_corporate_packages()
        if flags["is_sales_user"]:
            return list_active_corporate_packages_for_sale_user(user=user)
        return list_active_corporate_packages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        flags = _package_list_role_flags(self.request.user)
        context.update(flags)
        context["available_contracts_for_link"] = list_contracts_available_for_his_package_link()
        context["available_schedule_configs_for_link"] = list_schedule_configs_available_for_his_package_link()
        return context


def _find_latest_checkin_for_patient(patient, schedule_config, exam_record):
    """Tìm CheckInRecord gần nhất của BN trong kỳ khám (dùng cùng logic với lookup_patient)."""
    from apps.reception.models import CheckInRecord

    if not patient:
        return None

    if schedule_config:
        existing = (
            CheckInRecord.objects
            .filter(his_patient_sync=patient, schedule_config=schedule_config)
            .order_by("-created_at")
            .first()
        )
        if not existing:
            existing = (
                CheckInRecord.objects
                .filter(
                    snapshot_ma_bn=patient.his_patient_code,
                    exam_date__range=[schedule_config.exam_start_date, schedule_config.exam_end_date],
                )
                .order_by("-exam_date", "-created_at")
                .first()
            )
        return existing

    if getattr(exam_record, "exam_date", None):
        return (
            CheckInRecord.objects
            .filter(snapshot_ma_bn=patient.his_patient_code, exam_date=exam_record.exam_date)
            .order_by("-created_at")
            .first()
        )
    return None


class CorporatePackageDetailView(LoginRequiredMixin, DetailView):
    model = HisCorporatePackageSync
    template_name = 'his_integration/staff/package_detail.html'
    context_object_name = 'package'

    def get_object(self):
        return get_object_or_404(
            corporate_package_detail_queryset(),
            pk=self.kwargs['pk']
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        package = self.object
        exam_records = list(list_exam_records_for_package(package=package))
        context['exam_records'] = exam_records
        context['stats'] = get_package_exam_record_stats(package=package)

        # ── Trạng thái checkin của từng BN ──────────────────────────────
        from apps.reception.models import CheckInRecord, CheckInStatus
        patient_sync_ids = [r.patient_sync_id for r in exam_records if r.patient_sync_id]
        checkin_status_by_patient = {}
        if patient_sync_ids:
            for ci in (
                CheckInRecord.objects
                .filter(his_patient_sync_id__in=patient_sync_ids)
                .order_by("his_patient_sync_id", "-created_at")
                .values("his_patient_sync_id", "status")
            ):
                pid = ci["his_patient_sync_id"]
                if pid not in checkin_status_by_patient:
                    checkin_status_by_patient[pid] = ci["status"]

        context["cancelled_patient_pks"] = {
            pid for pid, s in checkin_status_by_patient.items() if s == CheckInStatus.CANCELLED
        }
        context["checkedin_patient_pks"] = {
            pid for pid, s in checkin_status_by_patient.items() if s == CheckInStatus.CHECKED_IN
        }
        context["checkedout_patient_pks"] = {
            pid for pid, s in checkin_status_by_patient.items() if s == CheckInStatus.CHECKED_OUT
        }
        context["is_it_admin_user"] = _is_it_admin(self.request.user)

        pkg_code = package.his_package_code or ''
        package_services = (
            HisPackageServiceSync.objects
            .filter(
                Q(his_package_code=pkg_code) |
                Q(his_package_code__startswith=pkg_code + '.'),
                is_active=True,
            )
            .select_related('service_catalog')
            .order_by('service_item_code')
        )
        groups_raw = defaultdict(list)
        for svc in package_services:
            group_code = (
                svc.service_catalog.service_group_code
                if svc.service_catalog and svc.service_catalog.service_group_code
                else 'N/A'
            )
            groups_raw[group_code].append({
                'code': svc.service_item_code,
                'name': svc.service_catalog.service_item_name if svc.service_catalog else svc.service_item_code,
                'unit': svc.unit or '',
                'quantity': float(svc.quantity),
                'unit_price': float(svc.unit_price),
                'is_outside_package': svc.is_outside_package,
                'his_package_code': svc.his_package_code or '',
            })

        sorted_groups = sorted(groups_raw.items())
        context['package_service_groups'] = [
            {
                'group_code': k,
                'count': len(v),
                'his_package_codes': sorted({s['his_package_code'] for s in v if s['his_package_code']}),
            }
            for k, v in sorted_groups
        ]
        context['package_service_total'] = sum(len(v) for _, v in sorted_groups)
        context['package_services_by_group'] = {k: v for k, v in sorted_groups}

        included_ultrasound_codes = set()
        for svc in package_services:
            if svc.is_outside_package or not svc.service_catalog:
                continue
            if _is_ultrasound_catalog(svc.service_catalog):
                included_ultrasound_codes.add((svc.service_item_code or "").strip())

        extra_imaging_items = list(
            HisDiagnosticImagingItemSync.objects.filter(
                is_active=True,
                imaging_sync__is_active=True,
                imaging_sync__exam_record_sync__package_sync=package,
                imaging_sync__exam_record_sync__patient_sync__isnull=False,
            ).select_related(
                'imaging_sync',
                'imaging_sync__exam_record_sync',
                'imaging_sync__exam_record_sync__patient_sync',
            ).order_by(
                'imaging_sync__exam_record_sync__exam_date',
                'imaging_sync__exam_record_sync__patient_sync__full_name',
                'service_item_code',
            )
        )
        extra_service_codes = {
            (item.service_item_code or "").strip()
            for item in extra_imaging_items
            if (item.service_item_code or "").strip()
        }
        catalog_map = {
            catalog.service_item_code: catalog
            for catalog in HisServiceCatalogSync.objects.filter(
                service_item_code__in=extra_service_codes,
                is_active=True,
            )
        }

        extra_rows_map = {}
        for item in extra_imaging_items:
            service_code = (item.service_item_code or "").strip()
            if not service_code or service_code in included_ultrasound_codes:
                continue

            service_catalog = catalog_map.get(service_code)
            if not _is_ultrasound_catalog(service_catalog):
                continue

            exam_record = item.imaging_sync.exam_record_sync
            patient = getattr(exam_record, 'patient_sync', None)
            if not exam_record or not patient:
                continue

            row_key = exam_record.pk
            service_name = _display_service_name(
                getattr(service_catalog, 'service_item_name', '') or service_code
            )
            service_key = _normalize_service_key(service_name)
            row = extra_rows_map.setdefault(
                row_key,
                {
                    'exam_record_id': exam_record.pk,
                    'patient_code': getattr(patient, 'his_patient_code', ''),
                    'patient_name': getattr(patient, 'full_name', ''),
                    'exam_date': getattr(exam_record, 'exam_date', None),
                    'services': [],
                    '_service_keys': set(),
                }
            )
            if service_key and service_key not in row['_service_keys']:
                row['_service_keys'].add(service_key)
                row['services'].append({
                    'code': service_code,
                    'name': service_name,
                })

        extra_rows = sorted(
            extra_rows_map.values(),
            key=lambda row: (
                row['exam_date'] or '',
                row['patient_name'] or '',
                row['patient_code'] or '',
            ),
        )
        for row in extra_rows:
            row.pop('_service_keys', None)

        context['extra_ultrasound_rows'] = extra_rows
        return context


class ExamRecordListView(LoginRequiredMixin, ListView):
    model = HisExamRecordSync
    template_name = 'his_integration/staff/exam_record_list.html'
    context_object_name = 'records'
    paginate_by = 100
    
    def get_queryset(self):
        package_id = self.request.GET.get('package')
        is_complete_param = self.request.GET.get('is_complete')
        quality_warning = self.request.GET.get('quality_warning', '').strip()
        is_complete = None
        if is_complete_param:
            is_complete = is_complete_param == 'true'

        qs = list_active_exam_records(
            package_id=package_id,
            is_complete=is_complete,
        )
        if quality_warning == 'exam_records_missing_patient':
            qs = qs.filter(patient_sync__isnull=True)
        elif quality_warning == 'exam_records_missing_package':
            qs = qs.filter(package_sync__isnull=True).exclude(raw_payload__MaGoiKhamTheoDoan__in=['', None])
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['packages'] = list_active_packages_for_filter()
        context['quality_warning'] = self.request.GET.get('quality_warning', '').strip()
        context['active_quality_warning'] = next(
            (warning for warning in get_his_sync_quality_warnings(sample_limit=1)
             if warning['key'] == self.request.GET.get('quality_warning', '').strip()),
            None,
        )
        return context


class ExamRecordDetailView(LoginRequiredMixin, DetailView):
    model = HisExamRecordSync
    template_name = 'his_integration/staff/exam_record_detail.html'
    context_object_name = 'record'

    def get_object(self):
        return get_object_or_404(
            exam_record_detail_queryset(),
            pk=self.kwargs['pk']
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.object
        context['diagnostic_imaging_records'] = (
            record.diagnostic_imaging_records
            .filter(is_active=True)
            .prefetch_related('items')
            .order_by('exam_date')
        )
        context['functional_test_records'] = (
            record.functional_test_records
            .filter(is_active=True)
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=HisFunctionalTestItemSync.objects
                        .filter(is_active=True)
                        .select_related('service_catalog')
                        .order_by('service_item_code'),
                )
            )
            .order_by('exam_date')
        )
        context['exam_service_items'] = (
            record.exam_service_items
            .filter(is_active=True)
            .select_related('service_catalog')
            .order_by('service_item_code')
        )
        return context


def trigger_sync(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    sync_type = request.POST.get('sync_type')
    run_inline = request.POST.get('run_inline') == 'true'
    source = request.POST.get('source')
    if not source:
        use_local_sync = run_inline and _is_local_sync_enabled()
        source = SOURCE_LOCAL_PG if use_local_sync else SOURCE_HIS_MSSQL

    if source not in {SOURCE_HIS_MSSQL, SOURCE_LOCAL_PG}:
        return JsonResponse({'error': 'Invalid sync source'}, status=400)

    if source == SOURCE_LOCAL_PG and not _is_local_sync_enabled():
        return JsonResponse({'error': 'Local HIS sync is disabled'}, status=403)

    if run_inline and source != SOURCE_LOCAL_PG and sync_type != 'patients':
        return JsonResponse({'error': 'Inline sync is only supported for patients'}, status=400)

    try:
        sync_result = dispatch_his_sync(
            sync_type=sync_type,
            actor=request.user,
            reset_cursor=request.POST.get('reset_cursor') == 'true',
            source=source,
            run_inline=(source == SOURCE_LOCAL_PG) or run_inline,
        )
    except InvalidHisSyncType:
        return JsonResponse({'error': 'Invalid sync_type'}, status=400)
    except Exception as exc:
        error_type, user_message = _classify_sync_exception(exc)
        logger.exception(
            "HIS sync trigger failed",
            extra={
                "sync_type": sync_type,
                "source": source,
                "user_id": getattr(request.user, "id", None),
                "username": getattr(request.user, "username", None),
                "error_type": error_type,
            },
        )
        return JsonResponse({
            'success': False,
            'error': user_message,
            'error_type': error_type,
        }, status=500)

    if not sync_result.get('success', True):
        error_message = sync_result.get('error') or 'Sync failed'
        logger.warning(
            "HIS sync trigger returned unsuccessful result",
            extra={
                "sync_type": sync_type,
                "source": source,
                "user_id": getattr(request.user, "id", None),
                "username": getattr(request.user, "username", None),
                "error": error_message,
            },
        )
        return JsonResponse({
            'success': False,
            'error': error_message,
            'error_type': 'sync_result_failed',
        }, status=500)
    
    return JsonResponse({
        'success': True,
        'task_id': sync_result['task_id'],
        'task_ids': sync_result.get('task_ids', [sync_result['task_id']] if sync_result.get('task_id') else []),
        'step_count': sync_result.get('step_count', 1),
        'inline': sync_result.get('inline', False),
        'message': f'Đã {"hoàn tất" if sync_result.get("inline") else "bắt đầu"} đồng bộ {sync_type}'
    })


@login_required(login_url="authentication:staff_login")
@require_POST
def link_package_contract(request, pk):
    if _is_executive(request.user):
        messages.error(request, "Trưởng bộ phận vận hành/kinh doanh sẽ thực hiện chức năng này.")
        return redirect("his_integration:package_list")
    try:
        link_contract_to_his_package(
            package_id=pk,
            contract_id=request.POST.get("contract_id"),
            actor=request.user,
        )
        messages.success(request, "Đã liên kết hợp đồng với gói khám HIS.")
    except HisPackageLinkingError as exc:
        messages.error(request, str(exc))

    return redirect("his_integration:package_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def link_package_schedule(request, pk):
    if _is_executive(request.user) or _is_sales(request.user):
        messages.error(request, "Trưởng bộ phận vận hành/kinh doanh sẽ thực hiện chức năng này.")
        return redirect("his_integration:package_list")
    try:
        link_schedule_config_to_his_package(
            package_id=pk,
            schedule_config_id=request.POST.get("schedule_config_id"),
            actor=request.user,
        )
        messages.success(request, "Đã liên kết lịch khám với gói khám HIS.")
    except HisPackageLinkingError as exc:
        messages.error(request, str(exc))

    return redirect("his_integration:package_list")


@login_required(login_url="authentication:staff_login")
@require_POST
def unlink_package_schedule(request, pk):
    flags = _package_list_role_flags(request.user)
    if not flags["can_unlink_schedule"]:
        messages.error(request, "Bạn không có quyền gỡ lịch khám.")
        return redirect("his_integration:package_list")
    try:
        unlink_schedule_config_from_his_package(
            package_id=pk,
            schedule_config_id=request.POST.get("schedule_config_id"),
            actor=request.user,
        )
        messages.success(request, "Đã gỡ lịch khám khỏi gói khám HIS.")
    except HisPackageLinkingError as exc:
        messages.error(request, str(exc))

    return redirect("his_integration:package_list")


# ── Hủy khám / Gỡ hủy / Gỡ check-in từ trang package_detail ────────────────

@login_required(login_url="authentication:staff_login")
@require_POST
def cancel_exam_record(request, pk):
    """Hủy khám cho BN trong gói — tạo hoặc cập nhật CheckInRecord sang CANCELLED."""
    from apps.reception.models import CheckInRecord, CheckInStatus
    from apps.scheduling.models import ContractScheduleConfig

    record = get_object_or_404(HisExamRecordSync, pk=pk)
    package = record.package_sync
    patient = record.patient_sync

    if not patient:
        messages.error(request, "Không tìm thấy thông tin bệnh nhân.")
        return redirect("his_integration:package_detail", pk=package.pk)

    schedule_config = (
        ContractScheduleConfig.objects.filter(his_package=package).first()
        if package else None
    )
    existing = _find_latest_checkin_for_patient(patient, schedule_config, record)

    if existing and existing.status == CheckInStatus.CHECKED_OUT:
        messages.error(request, f"{patient.full_name} đã hoàn thành khám, không thể hủy.")
    elif existing and existing.status == CheckInStatus.CHECKED_IN:
        messages.error(request, f"{patient.full_name} đang check-in. Chỉ IT Admin / Superuser có thể gỡ check-in.")
    elif existing and existing.status == CheckInStatus.CANCELLED:
        messages.info(request, f"{patient.full_name} đã ở trạng thái hủy khám rồi.")
    elif existing and existing.status == CheckInStatus.DEFERRED:
        existing.status = CheckInStatus.CANCELLED
        existing.operator = request.user
        existing.save(update_fields=["status", "operator", "updated_at"])
        messages.success(request, f"Đã hủy khám cho {patient.full_name}.")
    else:
        exam_dt = getattr(record, "exam_date", None) or date.today()
        company_name = getattr(package, "company_name", "") if package else ""
        CheckInRecord.objects.create(
            his_patient_sync=patient,
            schedule_config=schedule_config,
            snapshot_ma_bn=patient.his_patient_code,
            snapshot_ho_ten=patient.full_name,
            snapshot_gioi_tinh=patient.gioi_tinh or "",
            snapshot_ngay_sinh=patient.ngay_sinh,
            snapshot_company_name=company_name,
            snapshot_exam_start=getattr(schedule_config, "exam_start_date", None),
            snapshot_exam_end=getattr(schedule_config, "exam_end_date", None),
            exam_date=exam_dt,
            status=CheckInStatus.CANCELLED,
            operator=request.user,
        )
        messages.success(request, f"Đã hủy khám cho {patient.full_name}.")

    return redirect("his_integration:package_detail", pk=package.pk)


@login_required(login_url="authentication:staff_login")
@require_POST
def uncancel_exam_record(request, pk):
    """Gỡ hủy khám — IT Admin / Superuser only."""
    if not _is_it_admin(request.user):
        messages.error(request, "Chỉ IT Admin / Superuser mới có quyền gỡ hủy khám.")
        record = get_object_or_404(HisExamRecordSync, pk=pk)
        return redirect("his_integration:package_detail", pk=record.package_sync.pk)

    from apps.reception.models import CheckInRecord, CheckInStatus

    record = get_object_or_404(HisExamRecordSync, pk=pk)
    patient = record.patient_sync
    package = record.package_sync

    if not patient:
        messages.error(request, "Không tìm thấy thông tin bệnh nhân.")
        return redirect("his_integration:package_detail", pk=package.pk)

    deleted_count, _ = CheckInRecord.objects.filter(
        his_patient_sync=patient,
        status=CheckInStatus.CANCELLED,
    ).delete()

    if deleted_count:
        messages.success(request, f"Đã gỡ hủy khám cho {patient.full_name}.")
    else:
        messages.info(request, "Không tìm thấy bản ghi hủy khám.")

    return redirect("his_integration:package_detail", pk=package.pk)


@login_required(login_url="authentication:staff_login")
@require_POST
def uncheckin_exam_record(request, pk):
    """Gỡ check-in — IT Admin / Superuser only."""
    if not _is_it_admin(request.user):
        messages.error(request, "Chỉ IT Admin / Superuser mới có quyền gỡ check-in.")
        record = get_object_or_404(HisExamRecordSync, pk=pk)
        return redirect("his_integration:package_detail", pk=record.package_sync.pk)

    from apps.reception.models import CheckInRecord, CheckInStatus

    record = get_object_or_404(HisExamRecordSync, pk=pk)
    patient = record.patient_sync
    package = record.package_sync

    if not patient:
        messages.error(request, "Không tìm thấy thông tin bệnh nhân.")
        return redirect("his_integration:package_detail", pk=package.pk)

    deleted_count, _ = CheckInRecord.objects.filter(
        his_patient_sync=patient,
        status=CheckInStatus.CHECKED_IN,
    ).delete()

    if deleted_count:
        messages.success(request, f"Đã gỡ check-in cho {patient.full_name}.")
    else:
        messages.info(request, "Không tìm thấy bản ghi check-in.")

    return redirect("his_integration:package_detail", pk=package.pk)
