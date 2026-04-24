from __future__ import annotations

from typing import Any
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

from apps.his_integration.models import (
    HisSyncState,
    HisPatientSync,
    HisPatientTypeSync,
    HisCorporatePackageSync,
    HisExamRecordSync,
    HisSyncJob,
)
from apps.his_integration.services.his_source_clients import (
    SOURCE_HIS_MSSQL,
    get_his_source_client,
    get_state_source_name,
)


def _to_int(value) -> int | None:
    """HIS đôi khi trả '' thay vì None cho IntegerField."""
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_date(value):
    """HIS đôi khi trả '' thay vì None cho DateField/DateTimeField."""
    if value is None or value == '':
        return None
    return value


def _to_bytes(value) -> bytes | None:
    """Chuẩn hoá giá trị binary từ HIS về bytes cho BinaryField.

    pyodbc trả bytes cho varbinary nhưng có thể trả str cho image/varchar(MAX).
    latin-1 ánh xạ trực tiếp 0-255 nên không mất dữ liệu.
    """
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode('latin-1')
    return None


def json_safe(data: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in data.items():
        if isinstance(value, (bytes, bytearray, memoryview)):
            safe[key] = f"<binary:{len(value)} bytes>"
        elif hasattr(value, 'isoformat'):
            safe[key] = value.isoformat()
        elif isinstance(value, Decimal):
            safe[key] = float(value)
        else:
            safe[key] = value
    return safe


@shared_task(bind=True, max_retries=3)
def sync_patient_types_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='patient_type',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    try:
        client = get_his_source_client(source=source)
        rows = client.fetch_patient_types()
        
        job.total_records = len(rows)
        job.save(update_fields=['total_records'])
        
        for data in rows:
            try:
                code = (data.get('MaDoiTuongBenhNhan') or '').strip()
                if not code:
                    continue
                
                HisPatientTypeSync.objects.update_or_create(
                    his_patient_type_code=code,
                    defaults={
                        'patient_type_name': data.get('TenDoiTuongBenhNhan') or '',
                        'description': data.get('MoTaDoiTuongBenhNhan') or '',
                        'has_card': data.get('bCoThe'),
                        'raw_payload': json_safe(data),
                        'last_synced_at': timezone.now(),
                    }
                )
                job.synced_records += 1
            except Exception as e:
                job.failed_records += 1
                job.error_log[str(data.get('MaDoiTuongBenhNhan') or 'unknown')] = str(e)

        client.close()
        
        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_patients_from_his(self, batch_size=500, reset_cursor=False, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='patient',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    try:
        state, _ = HisSyncState.objects.get_or_create(
            source=get_state_source_name(source=source, base_source='his_dmbenhnhan')
        )
        
        if reset_cursor:
            state.last_auto_id = 0
            state.save(update_fields=['last_auto_id'])
        
        client = get_his_source_client(source=source)
        
        last_seen_auto_id = state.last_auto_id
        
        while True:
            rows = client.fetch_patients_batch(
                last_auto_id=last_seen_auto_id,
                batch_size=batch_size,
            )
            
            if not rows:
                break
            
            for data in rows:
                try:
                    his_code = (data.get('MaBenhNhan') or '').strip()
                    if not his_code:
                        continue
                    
                    auto_id = int(data.get('MaBenhNhanTuSinh') or 0)
                    last_seen_auto_id = max(last_seen_auto_id, auto_id)

                    ngay_cap = _to_date(data.get('NgayCapCMT') or data.get('NgayCap'))

                    HisPatientSync.objects.update_or_create(
                        his_patient_code=his_code,
                        defaults={
                            'his_patient_auto_id': auto_id,
                            'stt': _to_int(data.get('STT')),
                            'his_sysdate': _to_date(data.get('sysdate')),
                            'full_name': data.get('TenBenhNhan') or '',
                            'birth_date_text': data.get('NgayThang') or '',
                            'birth_year': _to_int(data.get('NamSinh')),
                            'gender_code': data.get('MaGioiTinh') or '',
                            'ethnicity_code': data.get('MaDanToc') or '',
                            'occupation_code': data.get('MaNgheNghiep') or '',
                            'country_code': data.get('MaQuocGia') or '',
                            'province_code': data.get('MaTinhThanh') or '',
                            'district_code': data.get('MaQuanHuyen') or '',
                            'ward_code': data.get('MaXa') or '',
                            'hamlet_address': data.get('ThonPho') or '',
                            'work_place': data.get('NoiLamViec') or '',
                            'phone': data.get('SoDienThoai') or '',
                            'phone_enabled': data.get('SoDienThoaiEnabled') or '',
                            'email': data.get('Email') or '',
                            'emergency_contact_name': data.get('NguoiCanBaoTin') or '',
                            'emergency_contact_phone': data.get('NguoiCanBaoTin_SDT') or '',
                            'fingerprint_1': _to_bytes(data.get('VanTay1')),
                            'fingerprint_2': _to_bytes(data.get('VanTay2')),
                            'fingerprint_3': _to_bytes(data.get('VanTay3')),
                            'patient_image': _to_bytes(data.get('HinhAnhBenhNhan')),
                            'patient_signature': _to_bytes(data.get('ChuKyBenhNhan')),
                            'relative_signature': _to_bytes(data.get('ChuKyNguoiNha')),
                            'outpatient_treatment_flag': data.get('bDieuTriNgoaiTru'),
                            'completed_treatment_flag': data.get('bDaDieuTriXong'),
                            'receive_online_result': data.get('NhanKetQuaOnline') or False,
                            'vip_flag': bool(data.get('bVip') or False),
                            'kiosk_checkin_flag': data.get('bTiepNhanKiot'),
                            'rank_code': data.get('MaCapBacCongTac') or '',
                            'unit_code': data.get('MaDonViCongTac') or '',
                            'employee_code': data.get('MaNhanVien') or '',
                            'client_source_code': data.get('MaNguonKhach') or '',
                            'vip_card_code': data.get('MaTheVip') or '',
                            'address': data.get('DiaChiBenhNhan') or '',
                            'full_address_label': data.get('TenXaPhuongQuanHuyenTinhThanh') or '',
                            'national_id': data.get('SoCMT') or '',
                            'national_id_issue_date': ngay_cap,
                            'national_id_issue_place': data.get('NoiCap') or '',
                            'national_id_issue_place_code': data.get('MaNoiCapCMT') or '',
                            'passport_number': data.get('SoHoChieu') or '',
                            'passport_issue_place': data.get('NoiCapHoChieu') or '',
                            'passport_issue_date': _to_date(data.get('NgayCapHoChieu')),
                            'hometown': data.get('QueQuan') or '',
                            'household_address': data.get('HoKhauTT') or '',
                            'enlist_date': _to_date(data.get('NgayNhapNgu')),
                            'discharge_date': _to_date(data.get('NgayXuatNgu')),
                            'reserve_date': _to_date(data.get('NgayTaiNgu')),
                            'family_status_code': data.get('IDTrangThaiGiaDinh') or '',
                            'age_in_months': _to_int(data.get('ThangTuoi')),
                            'age_in_weeks': _to_int(data.get('TuanTuoi')),
                            'age_in_hours': _to_int(data.get('GioTuoi')),
                            'chronic_disease_flag': data.get('BenhManTinh'),
                            'long_term_treatment_flag': data.get('DieuTriDaiNgay'),
                            'old_province_code': data.get('MaTinhThanhCu') or '',
                            'old_district_code': data.get('MaQuanHuyenCu') or '',
                            'old_ward_code': data.get('MaXaCu') or '',
                            'old_address': data.get('DiaChiCu') or '',
                            'server_source': data.get('TuMayChu') or '',
                            'note': data.get('GhiChu') or '',
                            'warning_note': data.get('LuuY') or '',
                            'password_raw': data.get('MatKhau') or '',
                            'raw_payload': json_safe(data),
                            'last_synced_at': timezone.now(),
                        }
                    )
                    
                    job.synced_records += 1
                    job.total_records += 1
                    
                except Exception as e:
                    job.failed_records += 1
                    job.error_log[his_code] = str(e)
            
            state.last_auto_id = last_seen_auto_id
            state.last_success_at = timezone.now()
            state.save(update_fields=['last_auto_id', 'last_success_at'])
        
        client.close()
        
        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_corporate_packages_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='corporate_package',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    try:
        client = get_his_source_client(source=source)
        rows = client.fetch_corporate_packages()
        
        job.total_records = len(rows)
        job.save(update_fields=['total_records'])
        
        for data in rows:
            try:
                code = (data.get('MaGoiKhamTheoDoan') or '').strip()
                if not code:
                    continue
                
                HisCorporatePackageSync.objects.update_or_create(
                    his_package_code=code,
                    defaults={
                        'package_name': data.get('TenGoiKhamTheoDoan') or '',
                        'company_name': data.get('TenCongTy') or '',
                        'company_address': data.get('DiaChiCongTy') or '',
                        'company_tax_code': data.get('MaSoThue') or '',
                        'exam_type': _to_int(data.get('HinhThucKhamTheoDoan')),
                        'discount_percentage': Decimal(str(data.get('PhanTramGiamGiaTheoDoan') or 0)),
                        'valid_from': _to_date(data.get('GioiHanTuNgay')),
                        'valid_to': _to_date(data.get('GioiHanDenNgay')),
                        'total_patients': data.get('SoLuongBenhNhan') or 0,
                        'client_source_code': data.get('MaNguonKhach') or '',
                        'exam_year': _to_int(data.get('NamKham')),
                        'exam_round': _to_int(data.get('DotKham')),
                        'exam_purpose': data.get('MucDichKham') or '',
                        'contract_number': data.get('SoHopDong') or '',
                        'contract_date': _to_date(data.get('NgayKyHopDong')),
                        'concluding_doctor': data.get('BacSyKetLuan') or '',
                        'conclusion': data.get('KetLuan') or '',
                        'package_group': data.get('NhomDoan') or '',
                        'image_data': _to_bytes(data.get('HinhAnh')),
                        'server_source': data.get('TuMayChu') or '',
                        'raw_payload': json_safe(data),
                        'last_synced_at': timezone.now(),
                    }
                )
                job.synced_records += 1
            except Exception as e:
                job.failed_records += 1
                job.error_log[code] = str(e)
        
        client.close()
        
        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_exam_records_from_his(self, batch_size=300, reset_cursor=False, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='exam_record',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    try:
        state, _ = HisSyncState.objects.get_or_create(
            source=get_state_source_name(source=source, base_source='his_hosokham')
        )
        
        if reset_cursor:
            state.last_auto_id = 0
            state.save(update_fields=['last_auto_id'])
        
        client = get_his_source_client(source=source)
        
        last_seen_auto_id = state.last_auto_id
        
        while True:
            rows = client.fetch_exam_records_batch(
                last_auto_id=last_seen_auto_id,
                batch_size=batch_size,
            )
            
            if not rows:
                break
            
            for data in rows:
                try:
                    record_code = (data.get('MaHoSo') or '').strip()
                    if not record_code:
                        continue
                    
                    auto_id = int(data.get('MaHoSoTuSinh') or 0)
                    last_seen_auto_id = max(last_seen_auto_id, auto_id)
                    
                    patient_code = (data.get('MaBenhNhan') or '').strip()
                    try:
                        patient_sync = HisPatientSync.objects.get(his_patient_code=patient_code)
                    except HisPatientSync.DoesNotExist:
                        job.failed_records += 1
                        job.error_log[record_code] = f"Patient {patient_code} not found"
                        continue
                    
                    package_code = (data.get('MaGoiKhamTheoDoan') or '').strip()
                    package_sync = None
                    if package_code:
                        try:
                            package_sync = HisCorporatePackageSync.objects.get(his_package_code=package_code)
                        except HisCorporatePackageSync.DoesNotExist:
                            pass
                    
                    patient_type_code = (data.get('MaDoiTuongBenhNhan') or '').strip()
                    patient_type_sync = None
                    if patient_type_code:
                        try:
                            patient_type_sync = HisPatientTypeSync.objects.get(his_patient_type_code=patient_type_code)
                        except HisPatientTypeSync.DoesNotExist:
                            pass
                    
                    vital_signs = {
                        'pulse': data.get('Mach'),
                        'temperature': data.get('NhietDo'),
                        'blood_pressure': data.get('HuyetAp'),
                        'respiratory_rate': data.get('NhipTho'),
                        'height': data.get('ChieuCao'),
                        'weight': data.get('CanNang'),
                        'bmi': data.get('BMI'),
                        'spo2': data.get('SPO2'),
                        'waist': data.get('VongBung'),
                    }
                    
                    clinical_exam = {
                        'general': data.get('ToanThan'),
                        'body_parts': data.get('CacBoPhan'),
                        'circulatory': data.get('TuanHoan'),
                        'respiratory': data.get('HoHap'),
                        'digestive': data.get('TieuHoa'),
                        'kidney_urinary': data.get('Than_TietNieu'),
                        'endocrine': data.get('NoiTiet'),
                        'musculoskeletal': data.get('Co_Xuong_Khop'),
                        'nervous': data.get('ThanKinh'),
                        'mental': data.get('TamThan'),
                        'external_eye': data.get('NgoaiMat'),
                        'intraoral': data.get('TrongMieng'),
                        'physical_classification': data.get('PhanLoaiTheLuc'),
                    }
                    
                    HisExamRecordSync.objects.update_or_create(
                        his_record_code=record_code,
                        defaults={
                            'his_record_auto_id': auto_id,
                            'his_admission_number': data.get('SoVaoVien') or '',
                            'patient_sync': patient_sync,
                            'package_sync': package_sync,
                            'patient_type_sync': patient_type_sync,
                            'exam_date': _to_date(data.get('NgayVaoKham')),
                            'exam_datetime': _to_date(data.get('NgayVaoKhamDP')),
                            'discharge_date': _to_date(data.get('NgayRaVien')),
                            'status_code': _to_int(data.get('TrangThaiPhieu')),
                            'payment_status': data.get('TrangThaiThanhToan') or False,
                            'reason_for_visit': data.get('LyDoVaoKham') or '',
                            'diagnosis': data.get('ChanDoan') or '',
                            'conclusion': data.get('KetLuan') or '',
                            'icd10_code_1': data.get('MaBenh1') or '',
                            'icd10_code_2': data.get('MaBenh2') or '',
                            'icd10_code_3': data.get('MaBenh3') or '',
                            'icd10_main': data.get('MaBenhChinh') or '',
                            'icd10_desc_1': data.get('GhiChuMaBenh1') or '',
                            'icd10_desc_2': data.get('GhiChuMaBenh2') or '',
                            'icd10_desc_3': data.get('GhiChuMaBenh3') or '',
                            'vital_signs': vital_signs,
                            'clinical_exam': clinical_exam,
                            'medical_history': data.get('TienSuBenhBanThan') or '',
                            'family_history': data.get('TienSuBenhGiaDinh') or '',
                            'disease_process': data.get('QuaTrinhBenhLy') or '',
                            'treatment_method': data.get('CachXuLy') or '',
                            'treatment_result': _to_int(data.get('KetQuaDieuTri')),
                            'doctor_code': data.get('MaBacSy') or '',
                            'receptionist_code': data.get('MaNguoiTiepNhan') or '',
                            'department_position': data.get('BoPhan') or '',
                            'job_title': data.get('ChucVu') or '',
                            'corporate_status': data.get('TrangThaiChiDinhDoan') or 0,
                            'corporate_arrival_status': data.get('TrangThaiHoSoDoanDenKham') or 0,
                            'number_issued_status': data.get('TrangThaiPhatSo') or 0,
                            'corporate_order_number': _to_int(data.get('STT_Doan')),
                            'corporate_barcode': data.get('Barcode_Doan') or '',
                            'checkin_state': _to_int(data.get('StateCheckIn')),
                            'health_classification': data.get('LoaiSucKhoe') or '',
                            'health_prediction': data.get('DuBaoSucKhoe') or '',
                            'prevention_advice': data.get('PhongNgua') or '',
                            'consultation_conclusion': data.get('KetLuanVaTuVan') or '',
                            'stt': _to_int(data.get('STT')),
                            'server_source': data.get('TuMayChu') or '',
                            'note': data.get('GhiChu') or '',
                            'internal_note': data.get('LuuYNoiBo') or '',
                            'raw_payload': json_safe(data),
                            'last_synced_at': timezone.now(),
                        }
                    )
                    
                    job.synced_records += 1
                    job.total_records += 1
                    
                except Exception as e:
                    job.failed_records += 1
                    job.error_log[record_code if 'record_code' in locals() else 'unknown'] = str(e)
            
            state.last_auto_id = last_seen_auto_id
            state.last_success_at = timezone.now()
            state.save(update_fields=['last_auto_id', 'last_success_at'])
        
        client.close()
        
        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)
