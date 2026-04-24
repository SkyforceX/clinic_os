from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView

from apps.his_integration.models import (
    HisSyncJob,
    HisCorporatePackageSync,
    HisExamRecordSync,
)
from apps.his_integration.selectors import (
    corporate_package_detail_queryset,
    exam_record_detail_queryset,
    get_his_sync_dashboard_stats,
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


class HisSyncDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'his_integration/staff/sync_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = get_his_sync_dashboard_stats()
        context['recent_jobs'] = list_recent_sync_jobs(limit=10)
        context['local_sync_enabled'] = settings.HIS_LOCAL_SYNC_ENABLED
        return context


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
        context['exam_records'] = list_exam_records_for_package(package=package)
        context['stats'] = get_package_exam_record_stats(package=package)
        return context


class ExamRecordListView(LoginRequiredMixin, ListView):
    model = HisExamRecordSync
    template_name = 'his_integration/staff/exam_record_list.html'
    context_object_name = 'records'
    paginate_by = 100
    
    def get_queryset(self):
        package_id = self.request.GET.get('package')
        is_complete_param = self.request.GET.get('is_complete')
        is_complete = None
        if is_complete_param:
            is_complete = is_complete_param == 'true'

        return list_active_exam_records(
            package_id=package_id,
            is_complete=is_complete,
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['packages'] = list_active_packages_for_filter()
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


def trigger_sync(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    sync_type = request.POST.get('sync_type')
    source = request.POST.get('source') or SOURCE_HIS_MSSQL

    if source not in {SOURCE_HIS_MSSQL, SOURCE_LOCAL_PG}:
        return JsonResponse({'error': 'Invalid sync source'}, status=400)

    if source == SOURCE_LOCAL_PG and not settings.HIS_LOCAL_SYNC_ENABLED:
        return JsonResponse({'error': 'Local HIS sync is disabled'}, status=403)

    try:
        sync_result = dispatch_his_sync(
            sync_type=sync_type,
            actor=request.user,
            reset_cursor=request.POST.get('reset_cursor') == 'true',
            source=source,
            run_inline=(source == SOURCE_LOCAL_PG),
        )
    except InvalidHisSyncType:
        return JsonResponse({'error': 'Invalid sync_type'}, status=400)

    if not sync_result.get('success', True):
        return JsonResponse({
            'success': False,
            'error': sync_result.get('error') or 'Sync failed',
        }, status=500)
    
    return JsonResponse({
        'success': True,
        'task_id': sync_result['task_id'],
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
