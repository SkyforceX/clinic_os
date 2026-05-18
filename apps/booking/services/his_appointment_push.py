import json
import logging
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime

import requests
from django.conf import settings
from django.db import connections
from django.utils import timezone

from apps.scheduling.models.schedule import TimeShift

logger = logging.getLogger(__name__)


@dataclass
class HisAppointmentPushResult:
    enabled: bool
    attempted: bool
    success: bool
    endpoint: str
    status_code: int | None = None
    skipped_reason: str = ""
    error: str = ""
    payload: dict | None = None
    response_data: object | None = None
    response_text: str = ""

    def to_session_dict(self):
        return asdict(self)


def _get_push_config():
    # Đọc cấu hình cho nhánh push HIS server thật từ settings/env.
    # Khi debug timeout hoặc sai endpoint, kiểm tra block config này trước.
    return getattr(settings, "HIS_APPOINTMENT_PUSH", {}) or {}


def _normalize_gender_code(value):
    raw = str(value or "").strip()
    if not raw:
        return ""

    normalized = raw.lower()
    mapping = {
        "male": "0",
        "nam": "0",
        "m": "0",
        "0": "0",
        "female": "1",
        "nu": "1",
        "nữ": "1",
        "f": "1",
        "1": "1",
        "other": "2",
        "khac": "2",
        "khác": "2",
        "2": "2",
    }
    return mapping.get(normalized, raw)


def _format_datetime_for_his(date_value, time_value):
    if not date_value:
        return ""
    return datetime.combine(date_value, datetime.strptime(time_value, "%H:%M:%S").time()).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _get_schedule_owner_name(schedule_slot):
    contract = getattr(schedule_slot, "contract", None)
    if getattr(getattr(contract, "company", None), "name", None):
        return contract.company.name

    quotation = getattr(schedule_slot, "quotation", None)
    if getattr(getattr(quotation, "company", None), "name", None):
        return quotation.company.name
    return getattr(quotation, "company_name", "") or ""


def _get_patient_source(appointment):
    return getattr(appointment, "his_patient_sync", None) or getattr(appointment, "patient", None)


def _get_birth_year(patient_source):
    birth_year = getattr(patient_source, "birth_year", None)
    if birth_year:
        return birth_year

    birth_date = getattr(patient_source, "ngay_sinh", None) or getattr(patient_source, "dob", None)
    if birth_date:
        return birth_date.year
    return 0


def _get_birth_text(patient_source):
    birth_text = getattr(patient_source, "birth_date_text", "") or ""
    if birth_text:
        return birth_text

    birth_date = getattr(patient_source, "ngay_sinh", None) or getattr(patient_source, "dob", None)
    if birth_date:
        return birth_date.strftime("%d/%m/%Y")
    return ""


def _get_patient_code(patient_source):
    return (
        getattr(patient_source, "his_patient_code", None)
        or getattr(patient_source, "ma_bn", None)
        or ""
    )


def _get_patient_name(patient_source):
    return (
        getattr(patient_source, "full_name", None)
        or getattr(patient_source, "ho_ten", None)
        or ""
    )


def _safe_json_response(response):
    try:
        return response.json()
    except ValueError:
        return None


def _is_his_success_response(response_data):
    if not isinstance(response_data, dict):
        return False

    his_code = response_data.get("code")
    if his_code == 0:
        return True

    message = str(response_data.get("msg") or "").strip().upper()
    data = response_data.get("data")
    return his_code == 1 and message == "OK" and data not in (None, "", [], {})


def build_his_appointment_push_body(appointment):
    # Chuẩn hóa dữ liệu Appointment nội bộ thành payload HIS theo spec
    # `API_DanhSachLichHen.Insert`.
    cfg = _get_push_config()
    patient_source = _get_patient_source(appointment)
    schedule_slot = getattr(appointment, "schedule_slot", None)
    if not patient_source or not schedule_slot:
        raise ValueError("Appointment thiếu bệnh nhân hoặc schedule slot để đồng bộ HIS.")

    shift = getattr(schedule_slot, "shift", "")
    if shift == TimeShift.MORNING:
        start_time = cfg.get("MORNING_START", "07:00:00")
        end_time = cfg.get("MORNING_END", "11:30:00")
    else:
        start_time = cfg.get("AFTERNOON_START", "13:00:00")
        end_time = cfg.get("AFTERNOON_END", "17:00:00")

    company_name = _get_schedule_owner_name(schedule_slot)
    patient_name = _get_patient_name(patient_source)
    patient_code = _get_patient_code(patient_source)
    birth_text = _get_birth_text(patient_source)
    birth_year = _get_birth_year(patient_source)
    note_default = cfg.get("DEFAULT_NOTE", "")
    note = note_default or f"Clinic OS appointment #{appointment.id}"
    content_default = cfg.get("DEFAULT_CONTENT", "Khám đoàn")
    content = content_default if not company_name else f"{content_default} - {company_name}"

    # Đây là object HIS sẽ dùng để map xuống DB của nó.
    # Khi đối chiếu với tài liệu field HIS, nhìn trực tiếp block này.
    lichhen = {
        "NgayBatDau": _format_datetime_for_his(schedule_slot.date, start_time),
        "NgayKetThuc": _format_datetime_for_his(schedule_slot.date, end_time),
        "MaBenhNhan": patient_code,
        "MaBacSy": cfg.get("DEFAULT_DOCTOR_CODE", ""),
        "MaKhoa": cfg.get("DEFAULT_DEPARTMENT_CODE", ""),
        "NoiDung": content,
        "NgayTao": timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S"),
        "TrangThai": 0,
        "Type": 1,
        "MaNguoiDung": cfg.get("DEFAULT_USER_CODE", ""),
        "MaNguonKhach": cfg.get("DEFAULT_CLIENT_SOURCE_CODE", ""),
        "LuuYNoiBo": "",
        "LyDoVaoKham": cfg.get("DEFAULT_REASON", ""),
        "GhiChu": note,
        "LoaiLichHen": cfg.get("DEFAULT_APPOINTMENT_TYPE", 0),
        "HoTen": patient_name,
        "NamSinh": birth_year,
        "SoDienThoai": getattr(patient_source, "phone", "") or "",
        "DiaChi": getattr(patient_source, "address", "") or "",
        "MaGioiTinh": _normalize_gender_code(
            getattr(patient_source, "gender_code", None) or getattr(patient_source, "gioi_tinh", None)
        ),
        "NgayThang": birth_text,
        "IDLichHenWeb": appointment.id,
    }
    # Payload hoàn chỉnh sẽ được gửi qua HTTP ở nhánh production.
    return {
        "sid": None,
        "cmd": cfg.get("CMD", "API_DanhSachLichHen.Insert"),
        "type": "DATATABLE",
        "data": {
            "lichhen": lichhen,
        },
    }


_HIS_LOCAL_PG_ALIAS = "his_local_pg"


def _ensure_his_local_pg_alias():
    # Tạo DB alias động cho local mode.
    # Nhánh này chỉ phục vụ dev/debug, không gọi HIS server thật.
    if _HIS_LOCAL_PG_ALIAS in connections.databases:
        return
    pg_cfg = settings.HIS_LOCAL_PG
    default_db = deepcopy(settings.DATABASES.get("default", {}))
    default_options = deepcopy(default_db.get("OPTIONS", {}))
    default_options["sslmode"] = "disable"
    default_db.update({
        "ENGINE": "django.db.backends.postgresql",
        "NAME": str(pg_cfg.get("NAME", "PK_HCM")),
        "USER": str(pg_cfg.get("USER", "postgres")),
        "PASSWORD": str(pg_cfg.get("PASSWORD", "postgres")),
        "HOST": str(pg_cfg.get("HOST", "127.0.0.1")),
        "PORT": int(pg_cfg.get("PORT", 5432)),
        "OPTIONS": default_options,
        "TIME_ZONE": getattr(settings, "TIME_ZONE", None),
    })
    connections.databases[_HIS_LOCAL_PG_ALIAS] = default_db


def _push_appointment_to_local_pg(appointment):
    """Dev-local fallback: INSERT vào ClinicOSLichHenLocal trong PK_HCM.

    Không dùng dbo.DanhSachLichHen (bảng sync từ MSSQL, schema không tương thích).
    Bảng ClinicOSLichHenLocal có cột lowercase PG-style, không phụ thuộc MSSQL schema.
    Production dùng HTTP POST → HIS AppService tự map JSON vào DB của nó.
    """
    pg_cfg = settings.HIS_LOCAL_PG
    schema = str(pg_cfg.get("SCHEMA", "dbo")).strip() or "dbo"
    table = f'{schema}."ClinicOSLichHenLocal"'
    endpoint = (
        f"local_pg://{pg_cfg.get('HOST', '127.0.0.1')}:{pg_cfg.get('PORT', 5432)}"
        f"/{pg_cfg.get('NAME', 'PK_HCM')}/{schema}.ClinicOSLichHenLocal"
    )

    try:
        # Local mode vẫn build đúng payload chuẩn HIS để debug mapping field
        # giống production, chỉ khác đích ghi dữ liệu.
        payload = build_his_appointment_push_body(appointment)
        lichhen = payload["data"]["lichhen"]
        _ensure_his_local_pg_alias()

        import json as _json
        insert_sql = f"""
            INSERT INTO {table} (
                appointment_id, ma_benh_nhan, ma_bac_sy, ma_khoa,
                ngay_bat_dau, ngay_ket_thuc, ngay_thang,
                noi_dung, ngay_tao,
                trang_thai, type,
                ma_nguoi_dung, ma_nguon_khach,
                luu_y_noi_bo, ly_do_vao_kham, ghi_chu,
                loai_lich_hen, ho_ten, nam_sinh,
                so_dien_thoai, dia_chi, ma_gioi_tinh,
                payload
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s
            ) RETURNING id
        """
        params = [
            lichhen.get("IDLichHenWeb") or None,
            lichhen.get("MaBenhNhan") or None,
            lichhen.get("MaBacSy") or None,
            lichhen.get("MaKhoa") or None,
            lichhen.get("NgayBatDau") or None,
            lichhen.get("NgayKetThuc") or None,
            lichhen.get("NgayThang") or None,
            lichhen.get("NoiDung") or None,
            lichhen.get("NgayTao") or None,
            int(lichhen.get("TrangThai", 0)),
            int(lichhen.get("Type", 1)),
            lichhen.get("MaNguoiDung") or None,
            lichhen.get("MaNguonKhach") or None,
            lichhen.get("LuuYNoiBo") or None,
            lichhen.get("LyDoVaoKham") or None,
            lichhen.get("GhiChu") or None,
            int(lichhen.get("LoaiLichHen", 0)),
            lichhen.get("HoTen") or None,
            lichhen.get("NamSinh") or None,
            lichhen.get("SoDienThoai") or None,
            lichhen.get("DiaChi") or None,
            lichhen.get("MaGioiTinh") or None,
            _json.dumps(payload, ensure_ascii=False),
        ]

        # Ghi trực tiếp vào PostgreSQL local để kiểm tra payload/mapping
        # mà không phụ thuộc network hay AppService HIS.
        with connections[_HIS_LOCAL_PG_ALIAS].cursor() as cursor:
            cursor.execute(insert_sql, params)
            row = cursor.fetchone()
            new_id = row[0] if row else None

        logger.info(
            "Local PG: inserted appointment %s → ClinicOSLichHenLocal id=%s",
            getattr(appointment, "id", None),
            new_id,
        )
        return HisAppointmentPushResult(
            enabled=True,
            attempted=True,
            success=True,
            endpoint=endpoint,
            status_code=None,
            payload=payload,
            response_data={"id": new_id, "source": "local_pg", "table": "ClinicOSLichHenLocal"},
            response_text="",
        )

    except Exception as exc:
        logger.warning(
            "Local PG: failed to insert appointment %s: %s",
            getattr(appointment, "id", None),
            exc,
            exc_info=True,
        )
        return HisAppointmentPushResult(
            enabled=True,
            attempted=True,
            success=False,
            endpoint=endpoint,
            payload=None,
            error=str(exc),
        )


def push_appointment_to_his(appointment, *, force=False):
    # Entry point chính của call flow push lịch hẹn sang HIS.
    # Cả tool demo trong `app api_his` và Celery task đều gọi vào đây.

    # Nhánh local/dev:
    # Nếu bật `HIS_LOCAL_SYNC_ENABLED`, hệ thống không bắn HTTP ra ngoài
    # mà insert payload vào bảng local để debug.
    if getattr(settings, "HIS_LOCAL_SYNC_ENABLED", False):
        return _push_appointment_to_local_pg(appointment)

    # Nhánh production/staging thật:
    # Từ đây trở xuống là luồng gọi HTTP sang HIS AppService.
    cfg = _get_push_config()
    endpoint = str(cfg.get("URL", "") or "").strip()
    enabled = bool(cfg.get("ENABLED")) or force
    payload = build_his_appointment_push_body(appointment)

    if not enabled:
        return HisAppointmentPushResult(
            enabled=False,
            attempted=False,
            success=False,
            endpoint=endpoint,
            skipped_reason="HIS appointment push is disabled.",
            payload=payload,
        )

    if not endpoint:
        return HisAppointmentPushResult(
            enabled=True,
            attempted=False,
            success=False,
            endpoint=endpoint,
            skipped_reason="Missing HIS appointment push URL.",
            payload=payload,
        )

    # Timeout cho request tới HIS server thật.
    # `ConnectTimeout`: chưa nối được host/port.
    # `ReadTimeout`: đã nối được nhưng HIS phản hồi quá chậm.
    timeout = int(cfg.get("TIMEOUT", 20) or 20)
    try:
        # Điểm bắn HTTP request thật sang HIS AppService.
        response = requests.post(endpoint, json=payload, timeout=timeout)
        response_data = _safe_json_response(response)
        response_text = ""
        if response_data is None:
            response_text = response.text[:4000]
        response.raise_for_status()

        # HIS có thể trả HTTP 200 nhưng business vẫn fail qua `code != 0`.
        his_code = response_data.get("code") if isinstance(response_data, dict) else None
        his_success = _is_his_success_response(response_data)
        his_error = ""
        if not his_success and isinstance(response_data, dict):
            his_error = response_data.get("msg") or f"HIS trả lỗi code={his_code}"

        logger.info(
            "Pushed appointment %s to HIS appointment API. status=%s his_code=%s response=%s",
            getattr(appointment, "id", None),
            response.status_code,
            his_code,
            json.dumps(response_data, ensure_ascii=False) if response_data is not None else response_text,
        )
        return HisAppointmentPushResult(
            enabled=True,
            attempted=True,
            success=his_success,
            endpoint=endpoint,
            status_code=response.status_code,
            payload=payload,
            response_data=response_data,
            response_text=response_text,
            error=his_error,
        )
    except requests.RequestException as exc:
        # Gom các lỗi network/timeout/HTTP vào một result để view/task
        # có thể log và hiển thị thống nhất khi debug.
        response = getattr(exc, "response", None)
        response_data = _safe_json_response(response) if response is not None else None
        response_text = ""
        status_code = None
        if response is not None:
            status_code = response.status_code
            if response_data is None:
                response_text = response.text[:4000]

        logger.warning(
            "Failed to push appointment %s to HIS appointment API: %s",
            getattr(appointment, "id", None),
            exc,
            exc_info=True,
        )
        return HisAppointmentPushResult(
            enabled=True,
            attempted=True,
            success=False,
            endpoint=endpoint,
            status_code=status_code,
            payload=payload,
            response_data=response_data,
            response_text=response_text,
            error=str(exc),
        )
