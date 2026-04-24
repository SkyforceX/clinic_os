from django.contrib import admin
from apps.his_integration.models import (
    HisSyncState,
    HisPatientSync,
    HisPatientTypeSync,
    HisCorporatePackageSync,
    HisExamRecordSync,
    HisSyncJob,
)

@admin.register(HisSyncState)
class HisSyncStateAdmin(admin.ModelAdmin):
    list_display = ['source', 'last_auto_id', 'last_success_at', 'updated_at']
    readonly_fields = ['updated_at']

@admin.register(HisPatientSync)
class HisPatientSyncAdmin(admin.ModelAdmin):
    list_display = ['his_patient_code', 'full_name', 'phone', 'birth_year', 'last_synced_at', 'is_active']
    list_filter = ['is_active', 'gender_code', 'vip_flag']
    search_fields = ['his_patient_code', 'full_name', 'phone', 'national_id']
    readonly_fields = ['last_synced_at']
    date_hierarchy = 'last_synced_at'

@admin.register(HisPatientTypeSync)
class HisPatientTypeSyncAdmin(admin.ModelAdmin):
    list_display = ['his_patient_type_code', 'patient_type_name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['his_patient_type_code', 'patient_type_name']

@admin.register(HisCorporatePackageSync)
class HisCorporatePackageSyncAdmin(admin.ModelAdmin):
    list_display = ['his_package_code', 'package_name', 'company_name', 'valid_from', 'valid_to', 'total_patients', 'contract', 'is_active']
    list_filter = ['is_active', 'valid_from', 'valid_to']
    search_fields = ['his_package_code', 'package_name', 'company_name']
    readonly_fields = ['last_synced_at']
    date_hierarchy = 'valid_from'

@admin.register(HisExamRecordSync)
class HisExamRecordSyncAdmin(admin.ModelAdmin):
    list_display = ['his_record_code', 'patient_sync', 'exam_date', 'package_sync', 'is_complete', 'is_active']
    list_filter = ['is_active', 'is_complete', 'exam_date']
    search_fields = ['his_record_code', 'patient_sync__full_name']
    readonly_fields = ['last_synced_at']
    date_hierarchy = 'exam_date'

@admin.register(HisSyncJob)
class HisSyncJobAdmin(admin.ModelAdmin):
    list_display = ['entity_type', 'status', 'total_records', 'synced_records', 'failed_records', 'started_at', 'completed_at', 'triggered_by']
    list_filter = ['entity_type', 'status', 'started_at']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'