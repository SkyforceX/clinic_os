from django.urls import path
from apps.his_integration.web.views import staff

app_name = 'his_integration'

urlpatterns = [
    path('', staff.HisSyncDashboardView.as_view(), name='dashboard'),
    path('quality/', staff.HisSyncQualityView.as_view(), name='quality'),
    path('quality/export/', staff.export_quality_warning_csv, name='quality_export'),
    path('jobs/', staff.HisSyncJobListView.as_view(), name='job_list'),
    path('jobs/<int:pk>/', staff.HisSyncJobDetailView.as_view(), name='job_detail'),
    path('packages/', staff.CorporatePackageListView.as_view(), name='package_list'),
    path('packages/<int:pk>/link-contract/', staff.link_package_contract, name='link_package_contract'),
    path('packages/<int:pk>/link-schedule/', staff.link_package_schedule, name='link_package_schedule'),
    path('packages/<int:pk>/unlink-schedule/', staff.unlink_package_schedule, name='unlink_package_schedule'),
    path('packages/<int:pk>/', staff.CorporatePackageDetailView.as_view(), name='package_detail'),
    path('exam-records/', staff.ExamRecordListView.as_view(), name='exam_record_list'),
    path('exam-records/<int:pk>/', staff.ExamRecordDetailView.as_view(), name='exam_record_detail'),
    path('exam-records/<int:pk>/cancel/', staff.cancel_exam_record, name='cancel_exam_record'),
    path('exam-records/<int:pk>/uncancel/', staff.uncancel_exam_record, name='uncancel_exam_record'),
    path('exam-records/<int:pk>/uncheckin/', staff.uncheckin_exam_record, name='uncheckin_exam_record'),
    path('trigger-sync/', staff.trigger_sync, name='trigger_sync'),
    path('data/<str:entity_type>/', staff.HisDataListView.as_view(), name='data_list'),
]
