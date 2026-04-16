from __future__ import annotations

from typing import Any

import pyodbc
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.patients.models import HisPatientSync, HisSyncState


class Command(BaseCommand):
    help = "Đồng bộ bệnh nhân từ HIS MSSQL dbo.DMBenhNhan vào clinic_os"

    batch_size = 300

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=self.batch_size,
            help="Số record lấy mỗi lần",
        )
        parser.add_argument(
            "--reset-cursor",
            action="store_true",
            help="Reset cursor về 0 trước khi sync",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        reset_cursor = options["reset_cursor"]

        state, _ = HisSyncState.objects.get_or_create(source="his_dmbenhnhan")

        if reset_cursor:
            state.last_auto_id = 0
            state.last_error = ""
            state.save(update_fields=["last_auto_id", "last_error", "updated_at"])
            self.stdout.write(self.style.WARNING("Đã reset cursor về 0"))

        try:
            conn = self._connect_his()
            cursor = conn.cursor()

            total_created = 0
            total_updated = 0
            last_seen_auto_id = state.last_auto_id

            while True:
                rows = self._fetch_batch(cursor, last_seen_auto_id, batch_size)
                if not rows:
                    break

                created_count, updated_count, max_auto_id = self._upsert_rows(rows)
                total_created += created_count
                total_updated += updated_count
                last_seen_auto_id = max_auto_id

                state.last_auto_id = last_seen_auto_id
                state.last_success_at = timezone.now()
                state.last_error = ""
                state.save(
                    update_fields=[
                        "last_auto_id",
                        "last_success_at",
                        "last_error",
                        "updated_at",
                    ]
                )

                self.stdout.write(
                    f"Synced batch: created={created_count}, "
                    f"updated={updated_count}, "
                    f"last_auto_id={last_seen_auto_id}"
                )

            cursor.close()
            conn.close()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Hoàn tất sync HIS patients. created={total_created}, updated={total_updated}"
                )
            )

        except Exception as exc:
            state.last_error = str(exc)
            state.save(update_fields=["last_error", "updated_at"])
            raise

    def _connect_his(self):
        his_cfg = settings.HIS_MSSQL

        driver = his_cfg.get("DRIVER", "{ODBC Driver 18 for SQL Server}")
        server = str(his_cfg.get("HIS_DB_HOST", "")).strip()
        port = str(his_cfg.get("HIS_DB_PORT", "")).strip()
        database = his_cfg.get("HIS_DB_NAME", "")
        uid = his_cfg.get("HIS_DB_USER", "")
        pwd = his_cfg.get("HIS_DB_PASSWORD", "")
        encrypt = str(his_cfg.get("ENCRYPT", "no")).strip()
        trust_cert = str(his_cfg.get("TRUST_SERVER_CERTIFICATE", "yes")).strip()
        timeout = int(his_cfg.get("TIMEOUT", 5))

        if not server:
            raise RuntimeError("Thiếu HIS_MSSQL['SERVER'].")

        server_part = f"{server},{port}" if port else server

        conn_str = (
            f"DRIVER={driver};"
            f"SERVER={server_part};"
            f"DATABASE={database};"
            f"UID={uid};"
            f"PWD={pwd};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust_cert};"
        )

        return pyodbc.connect(conn_str, timeout=timeout)

    def _fetch_batch(self, cursor, last_auto_id: int, batch_size: int):
        query = f"""
        SELECT TOP ({batch_size})
            MaBenhNhan,
            TenBenhNhan,
            NgayThang,
            NamSinh,
            MaGioiTinh,
            MaDanToc,
            MaNgheNghiep,
            MaQuocGia,
            MaTinhThanh,
            MaQuanHuyen,
            ThonPho,
            NoiLamViec,
            SoDienThoai,
            Email,
            MaBenhNhanTuSinh,
            STT,
            sysdate,
            NguoiCanBaoTin,
            VanTay1,
            VanTay2,
            VanTay3,
            bDieuTriNgoaiTru,
            bDaDieuTriXong,
            MaXa,
            HinhAnhBenhNhan,
            MaCapBacCongTac,
            MaDonViCongTac,
            DiaChiBenhNhan,
            TenXaPhuongQuanHuyenTinhThanh,
            SoCMT,
            NgayCap,
            NoiCap,
            NgayNhapNgu,
            NgayXuatNgu,
            NgayTaiNgu,
            QueQuan,
            MaNguonKhach,
            SoHoChieu,
            NoiCapHoChieu,
            NgayCapHoChieu,
            MaNhanVien,
            IDTrangThaiGiaDinh,
            TuMayChu,
            MaTheVip,
            ThangTuoi,
            TuanTuoi,
            GioTuoi,
            NgayCapCMT,
            MaNoiCapCMT,
            GhiChu,
            HoKhauTT,
            BenhManTinh,
            LuuY,
            DieuTriDaiNgay,
            MatKhau,
            NhanKetQuaOnline,
            bVip,
            NguoiCanBaoTin_SDT,
            ChuKyBenhNhan,
            ChuKyNguoiNha,
            bTiepNhanKiot,
            MaTinhThanhCu,
            MaQuanHuyenCu,
            MaXaCu,
            DiaChiCu,
            SoDienThoaiEnabled
        FROM dbo.DMBenhNhan
        WHERE MaBenhNhanTuSinh > ?
        ORDER BY MaBenhNhanTuSinh ASC
        """
        cursor.execute(query, last_auto_id)
        return cursor.fetchall()

    @transaction.atomic
    def _upsert_rows(self, rows) -> tuple[int, int, int]:
        created_count = 0
        updated_count = 0
        max_auto_id = 0

        columns = [col[0] for col in rows[0].cursor_description]

        for row in rows:
            data = dict(zip(columns, row))
            max_auto_id = max(max_auto_id, int(data["MaBenhNhanTuSinh"] or 0))

            his_code = (data.get("MaBenhNhan") or "").strip()
            if not his_code:
                continue

            defaults = self._map_defaults(data)

            obj, created = HisPatientSync.objects.update_or_create(
                his_patient_code=his_code,
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count, max_auto_id

    def _map_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        ngay_cap = data.get("NgayCapCMT") or data.get("NgayCap")

        return {
            "his_patient_auto_id": data.get("MaBenhNhanTuSinh"),
            "stt": data.get("STT"),
            "his_sysdate": data.get("sysdate"),
            "full_name": data.get("TenBenhNhan"),
            "birth_date_text": data.get("NgayThang"),
            "birth_year": data.get("NamSinh"),
            "gender_code": data.get("MaGioiTinh"),
            "ethnicity_code": data.get("MaDanToc"),
            "occupation_code": data.get("MaNgheNghiep"),
            "country_code": data.get("MaQuocGia"),
            "province_code": data.get("MaTinhThanh"),
            "district_code": data.get("MaQuanHuyen"),
            "ward_code": data.get("MaXa"),
            "hamlet_address": data.get("ThonPho"),
            "work_place": data.get("NoiLamViec"),
            "phone": data.get("SoDienThoai"),
            "phone_enabled": data.get("SoDienThoaiEnabled"),
            "email": data.get("Email"),
            "emergency_contact_name": data.get("NguoiCanBaoTin"),
            "emergency_contact_phone": data.get("NguoiCanBaoTin_SDT"),
            "fingerprint_1": data.get("VanTay1"),
            "fingerprint_2": data.get("VanTay2"),
            "fingerprint_3": data.get("VanTay3"),
            "patient_image": data.get("HinhAnhBenhNhan"),
            "patient_signature": data.get("ChuKyBenhNhan"),
            "relative_signature": data.get("ChuKyNguoiNha"),
            "outpatient_treatment_flag": data.get("bDieuTriNgoaiTru"),
            "completed_treatment_flag": data.get("bDaDieuTriXong"),
            "receive_online_result": data.get("NhanKetQuaOnline"),
            "vip_flag": bool(data.get("bVip") or False),
            "kiosk_checkin_flag": data.get("bTiepNhanKiot"),
            "rank_code": data.get("MaCapBacCongTac"),
            "unit_code": data.get("MaDonViCongTac"),
            "employee_code": data.get("MaNhanVien"),
            "client_source_code": data.get("MaNguonKhach"),
            "vip_card_code": data.get("MaTheVip"),
            "address": data.get("DiaChiBenhNhan"),
            "full_address_label": data.get("TenXaPhuongQuanHuyenTinhThanh"),
            "national_id": data.get("SoCMT"),
            "national_id_issue_date": ngay_cap,
            "national_id_issue_place": data.get("NoiCap"),
            "national_id_issue_place_code": data.get("MaNoiCapCMT"),
            "passport_number": data.get("SoHoChieu"),
            "passport_issue_place": data.get("NoiCapHoChieu"),
            "passport_issue_date": data.get("NgayCapHoChieu"),
            "hometown": data.get("QueQuan"),
            "household_address": data.get("HoKhauTT"),
            "enlist_date": data.get("NgayNhapNgu"),
            "discharge_date": data.get("NgayXuatNgu"),
            "reserve_date": data.get("NgayTaiNgu"),
            "family_status_code": data.get("IDTrangThaiGiaDinh"),
            "age_in_months": data.get("ThangTuoi"),
            "age_in_weeks": data.get("TuanTuoi"),
            "age_in_hours": data.get("GioTuoi"),
            "chronic_disease_flag": data.get("BenhManTinh"),
            "long_term_treatment_flag": data.get("DieuTriDaiNgay"),
            "old_province_code": data.get("MaTinhThanhCu"),
            "old_district_code": data.get("MaQuanHuyenCu"),
            "old_ward_code": data.get("MaXaCu"),
            "old_address": data.get("DiaChiCu"),
            "server_source": data.get("TuMayChu"),
            "note": data.get("GhiChu"),
            "warning_note": data.get("LuuY"),
            "password_raw": data.get("MatKhau"),
            "raw_payload": self._json_safe(data),
            "last_synced_at": timezone.now(),
        }

    def _json_safe(self, data: dict[str, Any]) -> dict[str, Any]:
        safe = {}
        for key, value in data.items():
            if isinstance(value, (bytes, bytearray, memoryview)):
                safe[key] = f"<binary:{len(value)} bytes>"
            elif hasattr(value, "isoformat"):
                safe[key] = value.isoformat()
            else:
                safe[key] = value
        return safe