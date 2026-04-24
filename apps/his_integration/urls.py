from django.urls import path
from apps.his_integration.web.views import staff

app_name = 'his_integration'

urlpatterns = [
    path('', staff.HisSyncDashboardView.as_view(), name='dashboard'),
    path('jobs/', staff.HisSyncJobListView.as_view(), name='job_list'),
    path('jobs/<int:pk>/', staff.HisSyncJobDetailView.as_view(), name='job_detail'),
    path('packages/', staff.CorporatePackageListView.as_view(), name='package_list'),
    path('packages/<int:pk>/link-contract/', staff.link_package_contract, name='link_package_contract'),
    path('packages/<int:pk>/link-schedule/', staff.link_package_schedule, name='link_package_schedule'),
    path('packages/<int:pk>/unlink-schedule/', staff.unlink_package_schedule, name='unlink_package_schedule'),
    path('packages/<int:pk>/', staff.CorporatePackageDetailView.as_view(), name='package_detail'),
    path('exam-records/', staff.ExamRecordListView.as_view(), name='exam_record_list'),
    path('exam-records/<int:pk>/', staff.ExamRecordDetailView.as_view(), name='exam_record_detail'),
    path('trigger-sync/', staff.trigger_sync, name='trigger_sync'),
]
