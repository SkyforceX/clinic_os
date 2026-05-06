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
    HisDiagnosticImagingSync,
    HisDiagnosticImagingItemSync,
    HisServiceCatalogSync,
    HisPackageServiceSync,
    HisFunctionalTestSync,
    HisFunctionalTestItemSync,
    HisExamServiceItemSync,
    HisAppointmentSync,
    HisInvoiceSync,
    HisInvoiceDetailSync,
    HisPatientTypeConfigSync,
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
    from django.utils.timezone import make_aware, is_naive
    import datetime
    if value is None or value == '':
        return None
    if isinstance(value, str):
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                value = datetime.datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            return value
    if isinstance(value, datetime.datetime) and is_naive(value):
        return make_aware(value)
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


def _to_decimal(value):
    if value is None or value == '':
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal('1') if value else Decimal('0')
    if isinstance(value, str):
        normalized = value.strip().replace(',', '')
        if not normalized:
            return Decimal('0')
        value = normalized
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return Decimal('0')


def _normalize_his_code(value) -> str:
    return str(value or '').strip()


def _resolve_package_sync(*, package_code: str):
    normalized_code = _normalize_his_code(package_code)
    if not normalized_code:
        return None

    package_sync = HisCorporatePackageSync.objects.filter(
        his_package_code=normalized_code
    ).first()
    if package_sync:
        return package_sync

    candidate = normalized_code
    while '.' in candidate:
        candidate = candidate.rsplit('.', 1)[0]
        package_sync = HisCorporatePackageSync.objects.filter(
            his_package_code=candidate
        ).first()
        if package_sync:
            return package_sync
    return None


def _build_exam_header_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    headers_by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        exam_code = _normalize_his_code(row.get('MaKhamBenh'))
        if exam_code:
            headers_by_code[exam_code] = row
    return headers_by_code


def _chunked_rows(rows: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    if chunk_size <= 0:
        chunk_size = 500
    return [rows[index:index + chunk_size] for index in range(0, len(rows), chunk_size)]


def _group_rows_by_code(rows: list[dict[str, Any]], *, field_name: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        code = _normalize_his_code(row.get(field_name))
        if not code:
            continue
        grouped.setdefault(code, []).append(row)
    return grouped


def _safe_close_client(client) -> None:
    if not client:
        return
    try:
        client.close()
    except Exception:
        pass
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


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


@shared_task(bind=True, max_retries=0)
def run_his_sync_sequence(
    self,
    *,
    sync_type: str,
    triggered_by_id: int | None = None,
    reset_cursor: bool = False,
    patient_batch_size: int = 500,
    exam_batch_size: int = 300,
    source: str = SOURCE_HIS_MSSQL,
):
    """
    Run an ordered sync sequence without letting one failed step cancel later steps.

    Production "sync all" uses Celery background execution; if we chain tasks directly,
    a single retry/failure prevents all remaining entity syncs from running. This
    wrapper preserves ordering while allowing later steps to continue and log their
    own HisSyncJob results.
    """
    from apps.his_integration.services.sync_orchestration import build_his_sync_steps

    steps = build_his_sync_steps(
        sync_type=sync_type,
        triggered_by_id=triggered_by_id,
        reset_cursor=reset_cursor,
        patient_batch_size=patient_batch_size,
        exam_batch_size=exam_batch_size,
        source=source,
    )

    results: list[dict[str, Any]] = []
    failed_steps: list[dict[str, Any]] = []

    for step in steps:
        result = step.task.apply(kwargs=step.kwargs)
        error = None if result.successful() else str(result.result)
        step_result = {
            "sync_type": step.sync_type,
            "label": step.label,
            "task_id": result.id,
            "success": result.successful(),
            "error": error,
        }
        results.append(step_result)
        if error:
            failed_steps.append(step_result)

    return {
        "sync_type": sync_type,
        "source": source,
        "step_count": len(steps),
        "success": not failed_steps,
        "results": results,
        "failed_steps": failed_steps,
    }


@shared_task(bind=True, max_retries=3)
def sync_patient_types_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='patient_type',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    client = None
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

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_patients_from_his(self, batch_size=500, reset_cursor=False, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='patient',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    client = None
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
        
        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_corporate_packages_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='corporate_package',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    client = None
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
        
        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_exam_records_from_his(self, batch_size=300, reset_cursor=False, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='exam_record',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    
    client = None
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
                    
                    package_code = _normalize_his_code(data.get('MaGoiKhamTheoDoan'))
                    package_sync = _resolve_package_sync(package_code=package_code)
                    
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
                            'doctor_name': data.get('TenBacSy') or '',
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
        
        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
        
    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_diagnostic_imaging_from_his(self, batch_size=300, reset_cursor=False, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='diagnostic_imaging',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )

    client = None
    try:
        state, _ = HisSyncState.objects.get_or_create(
            source=get_state_source_name(source=source, base_source='his_cdha_detail')
        )

        if reset_cursor:
            state.last_auto_id = 0
            state.save(update_fields=['last_auto_id'])

        client = get_his_source_client(source=source)
        last_seen_auto_id = state.last_auto_id

        while True:
            detail_rows = client.fetch_diagnostic_imaging_details_batch(
                last_auto_id=last_seen_auto_id,
                batch_size=batch_size,
            )
            if not detail_rows:
                break

            imaging_codes = []
            details_by_code: dict[str, list[dict[str, Any]]] = {}
            for detail in detail_rows:
                detail_auto_id = int(detail.get('IDChanDoanHinhAnh') or 0)
                last_seen_auto_id = max(last_seen_auto_id, detail_auto_id)

                imaging_code = (detail.get('MaChanDoanHinhAnh') or '').strip()
                if not imaging_code:
                    continue

                if imaging_code not in details_by_code:
                    imaging_codes.append(imaging_code)
                    details_by_code[imaging_code] = []
                details_by_code[imaging_code].append(detail)

            headers_by_code: dict[str, dict[str, Any]] = {}
            for imaging_code_chunk in _chunked_rows(
                [{'code': code} for code in imaging_codes],
                500,
            ):
                chunk_codes = [item['code'] for item in imaging_code_chunk]
                header_rows = client.fetch_diagnostic_imaging_by_codes(imaging_codes=chunk_codes)
                headers_by_code.update({
                    (row.get('MaChanDoanHinhAnh') or '').strip(): row
                    for row in header_rows
                    if (row.get('MaChanDoanHinhAnh') or '').strip()
                })

            for imaging_code in imaging_codes:
                try:
                    header = headers_by_code.get(imaging_code)
                    if not header:
                        job.failed_records += 1
                        job.error_log[imaging_code] = 'Header not found'
                        continue

                    record_code = (header.get('MaHoSo') or '').strip()
                    exam_record_sync = None
                    patient_sync = None
                    if record_code:
                        exam_record_sync = HisExamRecordSync.objects.filter(
                            his_record_code=record_code
                        ).select_related('patient_sync').first()
                        if exam_record_sync:
                            patient_sync = exam_record_sync.patient_sync

                    imaging_sync, _ = HisDiagnosticImagingSync.objects.update_or_create(
                        his_imaging_code=imaging_code,
                        defaults={
                            'his_admission_number': header.get('SoVaoVien') or '',
                            'exam_record_sync': exam_record_sync,
                            'patient_sync': patient_sync,
                            'sequence_number': _to_int(header.get('STT')),
                            'daily_sequence_number': _to_int(header.get('STTNgay')),
                            'internal_sequence_number': _to_int(header.get('iSTT')),
                            'exam_date': _to_date(header.get('NgayVaoKham')),
                            'ordered_at': _to_date(header.get('NgayGioYLenh')),
                            'performed_at': _to_date(header.get('NgayThucHien')),
                            'performed_dispatch_at': _to_date(header.get('NgayThucHienDP')),
                            'machine_received_at': _to_date(header.get('NgayVaoMay')),
                            'dispatch_at': _to_date(header.get('NgayDieuPhoi')),
                            'his_sysdate': _to_date(header.get('sysdate')),
                            'request_text': header.get('YeuCau') or '',
                            'note': header.get('GhiChu') or '',
                            'result_rtf': header.get('KetQua') or '',
                            'result_text': header.get('KetQuaText') or '',
                            'result_html': header.get('KetQuaHtml') or '',
                            'conclusion': header.get('KetLuan') or '',
                            'ordering_doctor_code': header.get('MaBacSyCD') or '',
                            'imaging_doctor_code': header.get('MaBacSyCDHA') or '',
                            'performing_doctor_code': header.get('MaBacSyTH') or '',
                            'user_code': header.get('MaNguoiDungCDHA') or '',
                            'status_code': _to_int(header.get('TrangThaiPhieu')),
                            'queue_status': _to_int(header.get('TrangThaiCho')),
                            'internal_status': _to_int(header.get('iTrangthai')),
                            'pacs_status': _to_int(header.get('iTrangThaiPacs')),
                            'clinical_department_code': header.get('MaKhoaCanLamSang') or '',
                            'clinical_room_code': header.get('MaPhongCanLamSang') or '',
                            'service_code': header.get('MaDichVu') or '',
                            'exam_department_code': header.get('MaKhoaKham') or '',
                            'exam_room_code': header.get('MaPhongKham') or '',
                            'machine_code': header.get('MaMayCLS') or '',
                            'result_template_code': header.get('MaPhieuKetQua') or '',
                            'image_1': header.get('Anh1') or '',
                            'image_2': header.get('Anh2') or '',
                            'image_3': header.get('Anh3') or '',
                            'image_4': header.get('Anh4') or '',
                            'sid_to_pacs': header.get('SIDToPACS') or '',
                            'printed_images': header.get('AnhDaIn') or '',
                            'size_13_18': _to_decimal(header.get('Size_13_18')),
                            'size_18_24': _to_decimal(header.get('Size_18_24')),
                            'size_24_30': _to_decimal(header.get('Size_24_30')),
                            'size_30_40': _to_decimal(header.get('Size_30_40')),
                            'is_voluntary': header.get('TuNguyen'),
                            'priority': _to_int(header.get('UuTien')),
                            'is_skipped': header.get('BoQua'),
                            'pushed_to_pacs': header.get('bDayPacs'),
                            'is_locked': header.get('bKhoaCLS'),
                            'auto_unlock': header.get('bTuDongMoKhoaCLS'),
                            'locked_at': _to_date(header.get('ThoiGianKhoa')),
                            'unlocked_at': _to_date(header.get('ThoiGianMoKhoa')),
                            'locked_by_code': header.get('MaNguoiKhoa') or '',
                            'raw_payload': json_safe(header),
                            'last_synced_at': timezone.now(),
                        }
                    )

                    for detail in details_by_code.get(imaging_code, []):
                        detail_auto_id = int(detail.get('IDChanDoanHinhAnh') or 0)
                        if not detail_auto_id:
                            continue

                        HisDiagnosticImagingItemSync.objects.update_or_create(
                            his_imaging_detail_auto_id=detail_auto_id,
                            defaults={
                                'imaging_sync': imaging_sync,
                                'service_item_code': detail.get('MaChiTieu') or '',
                                'unit_price': _to_decimal(detail.get('DonGia')),
                                'collected_amount': _to_decimal(detail.get('DaThuTien')),
                                'quantity': _to_decimal(detail.get('SoLuong')),
                                'performed_quantity': _to_decimal(detail.get('SoLuongThucHien')),
                                'note': detail.get('GhiChu') or '',
                                'his_sysdate': _to_date(detail.get('sysdate')),
                                'is_package_service': detail.get('TronGoi'),
                                'send_status': _to_int(detail.get('TrangThaiGui')),
                                'pushed_to_pacs': detail.get('DaDayPAC'),
                                'qr_code': detail.get('QRCode') or '',
                                'raw_payload': json_safe(detail),
                                'last_synced_at': timezone.now(),
                            }
                        )

                    job.synced_records += 1
                    job.total_records += 1
                except Exception as e:
                    job.failed_records += 1
                    job.error_log[imaging_code or 'unknown'] = str(e)

            state.last_auto_id = last_seen_auto_id
            state.last_success_at = timezone.now()
            state.save(update_fields=['last_auto_id', 'last_success_at'])

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()

    except Exception as e:
        job.status = 'FAILED'
        job.error_log['global'] = str(e)
        job.save()
        raise self.retry(exc=e, countdown=300)
    finally:
        _safe_close_client(client)


# ---------------------------------------------------------------------------
# Các task mới cho 7 entity types bổ sung
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3)
def sync_service_catalog_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='service_catalog',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    client = None
    try:
        client = get_his_source_client(source=source)
        rows = client.fetch_service_catalog()
        job.total_records = len(rows)
        job.save(update_fields=['total_records'])

        for data in rows:
            try:
                code = (data.get('MaChiTieu') or '').strip()
                if not code:
                    continue
                HisServiceCatalogSync.objects.update_or_create(
                    service_item_code=code,
                    defaults={
                        'service_item_name': data.get('TenChiTieu') or '',
                        'service_item_name_order': data.get('TenChiTieuChiDinh') or '',
                        'service_group_code': data.get('MaDichVu') or '',
                        'service_sub_group_code': data.get('MaNhomDMDichVuChiTiet') or '',
                        'report_group_code': data.get('MaDichVuBaoCao') or '',
                        'result_print_group_code': data.get('MaNhomInKQXetNghiem') or '',
                        'common_group_code': data.get('MaNhomDichVuChung') or '',
                        'unit': data.get('DonVi') or '',
                        'result_unit': data.get('DonViTraKQ') or '',
                        'sort_order': _to_int(data.get('SoThuTu')) or 0,
                        'sort_order_tb': _to_int(data.get('STT_TB')) or 0,
                        'normal_value': data.get('TriSoBinhThuong') or '',
                        'normal_value_male': data.get('TriSoBinhThuongNam') or '',
                        'normal_value_female': data.get('TriSoBinhThuongNu') or '',
                        'result_template_code': data.get('MaKetQuaMau') or '',
                        'is_high_tech': bool(data.get('DichVuKyThuatCao') or False),
                        'is_insurance_excluded': bool(data.get('BHKhongThanhToan') or False),
                        'is_no_discount': bool(data.get('KhongGiamGia') or False),
                        'is_no_sample': bool(data.get('KhongLayMau') or False),
                        'is_pay_once': bool(data.get('ThanhToanMotLan') or False),
                        'is_at_bed': bool(data.get('ThucHienTaiGiuong') or False),
                        'is_batch_perform': bool(data.get('bThucHienGop') or False),
                        'is_out_of_bh': bool(data.get('GDNgoaiBH') or False),
                        'lis_code': data.get('MaLIS') or '',
                        'lis_machine_code': data.get('MaMayLIS') or '',
                        'cls_machine_code': data.get('MaMayCLS') or '',
                        'surgery_group_id': _to_int(data.get('IDNhomPhauThuat')) or 0,
                        'byt_code': data.get('MaChiTieu_BYT') or '',
                        'bh_code': data.get('MaChiTieu_BH') or '',
                        'syt_code': data.get('MaXetNghiem_SYT') or '',
                        'common_item_code': data.get('MaChiTieuChung') or '',
                        'common_index_code': data.get('MaChiSoChung') or '',
                        'xn_index_code': data.get('MaChiSoXN') or '',
                        'xml_group_code': data.get('MaNhomXML') or '',
                        'surgery_type_code': data.get('MaLoaiPTTT') or '',
                        'expected_duration': _to_int(data.get('ThoiGianThucHienDuKien')) or 0,
                        'radiation_count': _to_int(data.get('SoLanPhatTia')) or 0,
                        'is_active_use': bool(data.get('TrangThaiSuDung') if data.get('TrangThaiSuDung') is not None else True),
                        'is_visible': bool(data.get('TrangThaiHienThi') if data.get('TrangThaiHienThi') is not None else True),
                        'raw_payload': json_safe(data),
                        'last_synced_at': timezone.now(),
                    }
                )
                job.synced_records += 1
            except Exception as e:
                job.failed_records += 1
                job.error_log[str(data.get('MaChiTieu') or 'unknown')] = str(e)

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
    except Exception as exc:
        job.status = 'FAILED'
        job.error_log['global'] = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_package_services_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='package_service',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    client = None
    try:
        client = get_his_source_client(source=source)
        rows = client.fetch_package_services()
        job.total_records = len(rows)
        job.save(update_fields=['total_records'])

        for data in rows:
            try:
                order_code = str(data.get('MaDon') or '').strip()
                if not order_code:
                    continue

                package_code = _normalize_his_code(data.get('MaGoiKhamTheoDoan'))
                package_sync = _resolve_package_sync(package_code=package_code)
                if package_sync is None and package_code:
                    job.error_log[f"warn:{order_code}"] = f"Package {package_code} not found, syncing without link"

                service_item_code = (data.get('MaChiTieu') or '').strip()
                service_catalog = HisServiceCatalogSync.objects.filter(
                    service_item_code=service_item_code
                ).first() if service_item_code else None

                HisPackageServiceSync.objects.update_or_create(
                    his_order_code=order_code,
                    defaults={
                        'his_package_code': package_code,
                        'package_sync': package_sync,
                        'service_catalog': service_catalog,
                        'service_item_code': service_item_code,
                        'unit': data.get('DonVi') or '',
                        'quantity': _to_decimal(data.get('SoLuong') or 1),
                        'unit_price': _to_decimal(data.get('DonGia') or 0),
                        'total_amount': _to_decimal(data.get('ThanhTien') or 0),
                        'room_code': data.get('MaPhong') or '',
                        'is_outside_package': bool(data.get('bNgoaiGoi') or False),
                        'is_selected': bool(data.get('bChonChiDinh') if data.get('bChonChiDinh') is not None else True),
                        'created_by': data.get('MaNguoiDung') or '',
                        'raw_payload': json_safe(data),
                        'last_synced_at': timezone.now(),
                    }
                )
                job.synced_records += 1
            except Exception as e:
                job.failed_records += 1
                job.error_log[str(data.get('MaDon') or 'unknown')] = str(e)

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
    except Exception as exc:
        job.status = 'FAILED'
        job.error_log['global'] = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_functional_tests_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='functional_test',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    client = None
    try:
        client = get_his_source_client(source=source)
        rows = client.fetch_functional_tests()
        job.total_records = len(rows)
        job.save(update_fields=['total_records'])
        for row_chunk in _chunked_rows(rows, 500):
            ft_codes = [
                _normalize_his_code(data.get('MaThamDoChucNang'))
                for data in row_chunk
                if _normalize_his_code(data.get('MaThamDoChucNang'))
            ]
            item_rows = client.fetch_functional_test_items_by_codes(ft_codes=ft_codes)
            items_by_code = _group_rows_by_code(item_rows, field_name='MaThamDoChucNang')

            for data in row_chunk:
                try:
                    ft_code = (data.get('MaThamDoChucNang') or '').strip()
                    if not ft_code:
                        continue

                    record_code = (data.get('MaHoSo') or '').strip()
                    exam_record_sync = None
                    patient_sync = None
                    if record_code:
                        exam_record_sync = HisExamRecordSync.objects.filter(
                            his_record_code=record_code
                        ).select_related('patient_sync').first()
                        if exam_record_sync:
                            patient_sync = exam_record_sync.patient_sync

                    ft_sync, _ = HisFunctionalTestSync.objects.update_or_create(
                        his_ft_code=ft_code,
                        defaults={
                            'his_admission_number': data.get('SoVaoVien') or '',
                            'exam_record_sync': exam_record_sync,
                            'patient_sync': patient_sync,
                            'sequence_number': _to_int(data.get('STT')),
                            'daily_sequence_number': _to_int(data.get('STTNgay')),
                            'exam_date': _to_date(data.get('NgayVaoKham')),
                            'ordered_at': _to_date(data.get('NgayGioYLenh')),
                            'performed_at': _to_date(data.get('NgayThucHien')),
                            'machine_received_at': _to_date(data.get('NgayVaoMay')),
                            'dispatch_at': _to_date(data.get('NgayDieuPhoi')),
                            'his_sysdate': _to_date(data.get('sysdate')),
                            'request_text': data.get('YeuCau') or '',
                            'note': data.get('GhiChu') or '',
                            'result_text': data.get('KetQuaText') or '',
                            'result_html': data.get('KetQuaHtml') or '',
                            'conclusion': data.get('KetLuan') or '',
                            'ordering_doctor_code': data.get('MaBacSyCD') or '',
                            'ft_doctor_code': data.get('MaBacSyTDCN') or '',
                            'performing_doctor_code': data.get('MaBacSyTH') or '',
                            'user_code': data.get('MaNguoiDungTDCN') or '',
                            'status_code': _to_int(data.get('TrangThaiPhieu')),
                            'queue_status': _to_int(data.get('TrangThaiCho')),
                            'internal_status': _to_int(data.get('iTrangthai')),
                            'pacs_status': _to_int(data.get('iTrangThaiPACS')),
                            'clinical_department_code': data.get('MaKhoaCanLamSang') or '',
                            'clinical_room_code': data.get('MaPhongCanLamSang') or '',
                            'service_code': data.get('MaDichVu') or '',
                            'exam_department_code': data.get('MaKhoaKham') or '',
                            'exam_room_code': data.get('MaPhongKham') or '',
                            'machine_code': data.get('MaMayCLS') or '',
                            'result_template_code': data.get('MaPhieuKetQua') or '',
                            'sid_to_pacs': data.get('SIDToPACS') or '',
                            'has_anesthesia': data.get('CoGayMe'),
                            'hp_test': data.get('TestNhanhHP'),
                            'hp_test_time': data.get('ThoiGianTestHP') or '',
                            'is_voluntary': data.get('TuNguyen'),
                            'priority': _to_int(data.get('UuTien')),
                            'is_skipped': data.get('BoQua'),
                            'pushed_to_pacs': data.get('bDayPacs'),
                            'raw_payload': json_safe(data),
                            'last_synced_at': timezone.now(),
                        }
                    )

                    for item in items_by_code.get(ft_code, []):
                        item_code = (item.get('MaChiTieu') or '').strip()
                        if not item_code:
                            continue
                        service_catalog = HisServiceCatalogSync.objects.filter(
                            service_item_code=item_code
                        ).first()
                        HisFunctionalTestItemSync.objects.update_or_create(
                            ft_sync=ft_sync,
                            service_item_code=item_code,
                            defaults={
                                'service_catalog': service_catalog,
                                'unit_price': _to_decimal(item.get('DonGia') or 0),
                                'collected_amount': _to_decimal(item.get('DaThuTien') or 0),
                                'quantity': _to_decimal(item.get('SoLuong') or 1),
                                'performed_quantity': _to_decimal(item.get('SoLuongThucHien') or 0),
                                'note': item.get('GhiChu') or '',
                                'his_sysdate': _to_date(item.get('sysdate')),
                                'is_package_service': item.get('TronGoi'),
                                'send_status': _to_int(item.get('TrangThaiGui')),
                                'raw_payload': json_safe(item),
                                'last_synced_at': timezone.now(),
                            }
                        )

                    job.synced_records += 1
                except Exception as e:
                    job.failed_records += 1
                    job.error_log[str(data.get('MaThamDoChucNang') or 'unknown')] = str(e)

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
    except Exception as exc:
        job.status = 'FAILED'
        job.error_log['global'] = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_exam_service_items_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='exam_service_item',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    client = None
    try:
        client = get_his_source_client(source=source)
        rows = client.fetch_exam_service_items()
        job.total_records = len(rows)
        job.save(update_fields=['total_records'])
        for row_chunk in _chunked_rows(rows, 500):
            exam_codes = sorted({
                _normalize_his_code(row.get('MaKhamBenh'))
                for row in row_chunk
                if _normalize_his_code(row.get('MaKhamBenh'))
            })
            exam_headers_by_code = _build_exam_header_map(
                client.fetch_exam_headers_by_codes(exam_codes=exam_codes)
            )

            for data in row_chunk:
                try:
                    ma_kham_benh = _normalize_his_code(data.get('MaKhamBenh'))
                    service_item_code = _normalize_his_code(data.get('MaChiTieu'))
                    if not ma_kham_benh or not service_item_code:
                        continue

                    exam_header = exam_headers_by_code.get(ma_kham_benh) or {}
                    record_code = _normalize_his_code(exam_header.get('MaHoSo'))
                    exam_record_sync = HisExamRecordSync.objects.filter(
                        his_record_code=record_code
                    ).first() if record_code else None

                    service_catalog = HisServiceCatalogSync.objects.filter(
                        service_item_code=service_item_code
                    ).first()

                    HisExamServiceItemSync.objects.update_or_create(
                        ma_kham_benh=ma_kham_benh,
                        service_item_code=service_item_code,
                        defaults={
                            'exam_record_sync': exam_record_sync,
                            'service_catalog': service_catalog,
                            'unit_price': _to_decimal(data.get('DonGia') or 0),
                            'collected_amount': _to_decimal(data.get('DaThuTien') or 0),
                            'quantity': _to_decimal(data.get('SoLuong')) if data.get('SoLuong') is not None else None,
                            'his_sysdate': _to_date(data.get('sysdate')),
                            'is_package_service': bool(data.get('TronGoi') or False),
                            'raw_payload': json_safe(data),
                            'last_synced_at': timezone.now(),
                        }
                    )
                    job.synced_records += 1
                except Exception as e:
                    job.failed_records += 1
                    key = f"{data.get('MaKhamBenh') or '?'}:{data.get('MaChiTieu') or '?'}"
                    job.error_log[key] = str(e)

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
    except Exception as exc:
        job.status = 'FAILED'
        job.error_log['global'] = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_appointments_from_his(self, batch_size=300, reset_cursor=False, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='appointment',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    client = None
    try:
        state, _ = HisSyncState.objects.get_or_create(
            source=get_state_source_name(source=source, base_source='his_lichhen')
        )
        if reset_cursor:
            state.last_auto_id = 0
            state.save(update_fields=['last_auto_id'])

        client = get_his_source_client(source=source)
        last_seen_auto_id = state.last_auto_id

        while True:
            rows = client.fetch_appointments_batch(
                last_auto_id=last_seen_auto_id,
                batch_size=batch_size,
            )
            if not rows:
                break

            for data in rows:
                try:
                    appt_id = _to_int(data.get('ID'))
                    if not appt_id:
                        continue
                    last_seen_auto_id = max(last_seen_auto_id, appt_id)

                    patient_code = (data.get('MaBenhNhan') or '').strip()
                    patient_sync = HisPatientSync.objects.filter(
                        his_patient_code=patient_code
                    ).first() if patient_code else None

                    record_code = (data.get('MaHoSo') or '').strip()
                    exam_record_sync = HisExamRecordSync.objects.filter(
                        his_record_code=record_code
                    ).first() if record_code else None

                    HisAppointmentSync.objects.update_or_create(
                        his_appointment_id=appt_id,
                        defaults={
                            'patient_sync': patient_sync,
                            'his_patient_code': patient_code,
                            'exam_record_sync': exam_record_sync,
                            'his_record_code': record_code,
                            'doctor_code': data.get('MaBacSy') or '',
                            'department_code': data.get('MaKhoa') or '',
                            'content': data.get('NoiDung') or '',
                            'start_datetime': _to_date(data.get('NgayBatDau')),
                            'end_datetime': _to_date(data.get('NgayKetThuc')),
                            'appointment_date': _to_date(data.get('NgayThang')),
                            'status': _to_int(data.get('TrangThai')) or 0,
                            'appointment_type': _to_int(data.get('LoaiLichHen')) or 0,
                            'created_at': _to_date(data.get('NgayTao')),
                            'created_by': data.get('MaNguoiDung') or '',
                            'sms_sent': bool(data.get('isDaGuiSMS') or False),
                            'message_id': _to_int(data.get('IDTinNhan')),
                            'web_booking_id': _to_int(data.get('IDLichHenWeb')),
                            'booking_code': data.get('BookingCode') or '',
                            'service_order_code': data.get('MaPhieuDichVu') or '',
                            'client_source_code': data.get('MaNguonKhach') or '',
                            'patient_name': data.get('HoTenBenhNhan') or '',
                            'birth_year': _to_int(data.get('NamSinh')),
                            'phone': data.get('SoDienThoai') or '',
                            'address': data.get('DiaChi') or '',
                            'gender_code': data.get('MaGioiTinh') or '',
                            'email': data.get('Email') or '',
                            'national_id': data.get('CCCD') or '',
                            'reason_for_visit': data.get('LyDoVaoKham') or '',
                            'note': data.get('GhiChu') or '',
                            'internal_note': data.get('LuuYNoiBo') or '',
                            'outsold_reason': data.get('LyDoOutsold') or '',
                            'days_count': _to_int(data.get('SoNgay')),
                            'raw_payload': json_safe(data),
                            'last_synced_at': timezone.now(),
                        }
                    )
                    job.synced_records += 1
                    job.total_records += 1
                except Exception as e:
                    job.failed_records += 1
                    job.error_log[str(data.get('ID') or 'unknown')] = str(e)

            state.last_auto_id = last_seen_auto_id
            state.last_success_at = timezone.now()
            state.save(update_fields=['last_auto_id', 'last_success_at'])

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
    except Exception as exc:
        job.status = 'FAILED'
        job.error_log['global'] = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_invoices_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='invoice',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    client = None
    try:
        client = get_his_source_client(source=source)
        invoice_rows = client.fetch_invoices()
        detail_rows = client.fetch_invoice_details()
        job.total_records = len(invoice_rows)
        job.save(update_fields=['total_records'])

        details_by_ref: dict[str, list] = {}
        for detail in detail_rows:
            ref_id = (detail.get('RefID') or '').strip()
            details_by_ref.setdefault(ref_id, []).append(detail)

        for data in invoice_rows:
            try:
                ref_id = (data.get('RefID') or '').strip()
                if not ref_id:
                    continue

                patient_code = (data.get('AccountObjectCode') or '').strip()
                patient_sync = HisPatientSync.objects.filter(
                    his_patient_code=patient_code
                ).first() if patient_code else None

                invoice_sync, _ = HisInvoiceSync.objects.update_or_create(
                    his_invoice_ref_id=ref_id,
                    defaults={
                        'ref_type': _to_int(data.get('RefType')) or 0,
                        'patient_sync': patient_sync,
                        'his_patient_code': patient_code,
                        'invoice_date': _to_date(data.get('InvDate')),
                        'customer_name': data.get('AccountObjectName') or '',
                        'customer_tax_code': data.get('AccountObjectTaxCode') or '',
                        'customer_email': data.get('AccountObjectEmail') or '',
                        'customer_address': data.get('AccountObjectAddress') or '',
                        'customer_bank_account': data.get('AccountObjectBankAccount') or '',
                        'customer_bank_name': data.get('AccountObjectBankName') or '',
                        'receiver_mobile': data.get('InvoiceReceiverMobile') or '',
                        'receiver_email': data.get('InvoiceReceiverEmail') or '',
                        'payment_method': data.get('PaymentMethod') or '',
                        'currency': data.get('CurrencyID') or 'VND',
                        'exchange_rate': str(data.get('ExchangeRate') or '1'),
                        'total_amount': _to_decimal(data.get('TotalAmount') or 0),
                        'total_sale_amount': _to_decimal(data.get('TotalSaleAmount') or 0),
                        'total_discount_amount': _to_decimal(data.get('TotalDiscountAmount') or 0),
                        'total_vat_amount': _to_decimal(data.get('TotalVATAmount') or 0),
                        'publish_status': _to_int(data.get('PublishStatus')) or 0,
                        'inv_template_no': data.get('InvTemplateNo') or '',
                        'inv_series': data.get('InvSeries') or '',
                        'inv_no': data.get('InvNo') or '',
                        'is_deleted': bool(data.get('IsInvoiceDeleted') or False),
                        'cashier_code': data.get('CustomInfo1') or '',
                        'cashier_name': data.get('CustomInfo2') or '',
                        'his_record_codes': data.get('MaHoSo') or '',
                        'patient_type_code': data.get('MaDoiTuong') or '',
                        'transaction_id': data.get('TransactionID') or '',
                        'einvoice_mapping_id': data.get('EinvoiceMappingID') or '',
                        'created_date': _to_date(data.get('CreatedDate')),
                        'modified_date': _to_date(data.get('ModifiedDate')),
                        'raw_payload': json_safe(data),
                        'last_synced_at': timezone.now(),
                    }
                )

                for detail in details_by_ref.get(ref_id, []):
                    detail_ref_id = (detail.get('RefDetailID') or '').strip()
                    if not detail_ref_id:
                        continue
                    HisInvoiceDetailSync.objects.update_or_create(
                        his_ref_detail_id=detail_ref_id,
                        defaults={
                            'invoice_sync': invoice_sync,
                            'inventory_item_id': detail.get('InventoryItemID') or '',
                            'inventory_item_code': detail.get('InventoryItemCode') or '',
                            'description': detail.get('Description') or '',
                            'unit_name': detail.get('UnitName') or '',
                            'quantity': _to_decimal(detail.get('Quantity') or 1),
                            'unit_price': _to_decimal(detail.get('UnitPrice') or 0),
                            'amount': _to_decimal(detail.get('Amount') or 0),
                            'discount_rate': _to_decimal(detail.get('DiscountRate') or 0),
                            'discount_amount': _to_decimal(detail.get('DiscountAmount') or 0),
                            'vat_rate': _to_decimal(detail.get('VatRate') or 0),
                            'vat_amount': _to_decimal(detail.get('VatAmount') or 0),
                            'sort_order': _to_int(detail.get('SortOrder')) or 0,
                            'is_promotion': bool(detail.get('IsPromotion') or False),
                            'inventory_item_type': _to_int(detail.get('InventoryItemType')) or 0,
                            'raw_payload': json_safe(detail),
                            'last_synced_at': timezone.now(),
                        }
                    )

                job.synced_records += 1
            except Exception as e:
                job.failed_records += 1
                job.error_log[str(data.get('RefID') or 'unknown')] = str(e)

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
    except Exception as exc:
        job.status = 'FAILED'
        job.error_log['global'] = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=300)
    finally:
        _safe_close_client(client)


@shared_task(bind=True, max_retries=3)
def sync_patient_type_configs_from_his(self, triggered_by_id=None, source=SOURCE_HIS_MSSQL):
    job = HisSyncJob.objects.create(
        entity_type='patient_type_config',
        status='RUNNING',
        started_at=timezone.now(),
        triggered_by_id=triggered_by_id,
    )
    client = None
    try:
        client = get_his_source_client(source=source)
        rows = client.fetch_patient_type_configs()
        job.total_records = len(rows)
        job.save(update_fields=['total_records'])

        for data in rows:
            try:
                config_id = _to_int(data.get('ID'))
                if not config_id:
                    continue

                type_code = (data.get('MaDoiTuongBenhNhan') or '').strip()
                try:
                    patient_type_sync = HisPatientTypeSync.objects.get(his_patient_type_code=type_code)
                except HisPatientTypeSync.DoesNotExist:
                    job.failed_records += 1
                    job.error_log[str(config_id)] = f"PatientType {type_code} not found"
                    continue

                HisPatientTypeConfigSync.objects.update_or_create(
                    his_config_id=config_id,
                    defaults={
                        'patient_type_sync': patient_type_sync,
                        'patient_type_code': type_code,
                        'business_rule_code': data.get('MaNghiepVu') or '',
                        'rule_value': data.get('MaXuLy') or '',
                        'raw_payload': json_safe(data),
                        'last_synced_at': timezone.now(),
                    }
                )
                job.synced_records += 1
            except Exception as e:
                job.failed_records += 1
                job.error_log[str(data.get('ID') or 'unknown')] = str(e)

        job.status = 'SUCCESS'
        job.completed_at = timezone.now()
        job.save()
    except Exception as exc:
        job.status = 'FAILED'
        job.error_log['global'] = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=300)
    finally:
        _safe_close_client(client)
