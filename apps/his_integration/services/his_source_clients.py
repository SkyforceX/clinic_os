from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import connections
from django.db.utils import DatabaseError, ProgrammingError


SOURCE_HIS_MSSQL = "his_mssql"
SOURCE_LOCAL_PG = "local_pg"


class HisSourceError(RuntimeError):
    pass


def normalize_batch_size(value: int | str | None, *, default: int) -> int:
    try:
        batch_size = int(value or default)
    except (TypeError, ValueError):
        batch_size = default
    return max(batch_size, 1)


def get_state_source_name(*, source: str, base_source: str) -> str:
    if source == SOURCE_HIS_MSSQL:
        return base_source
    return f"{base_source}_{source}"


def get_his_source_client(*, source: str = SOURCE_HIS_MSSQL):
    if source == SOURCE_HIS_MSSQL:
        return MssqlHisSourceClient()
    if source == SOURCE_LOCAL_PG:
        return LocalPostgresHisSourceClient()
    raise HisSourceError(f"Unknown HIS sync source: {source}")


class MssqlHisSourceClient:
    IN_CLAUSE_BATCH_SIZE = 1000

    def __init__(self):
        try:
            import pyodbc
        except ImportError as exc:
            raise HisSourceError("Missing pyodbc for HIS MSSQL sync") from exc

        his_cfg = settings.HIS_MSSQL
        driver = str(his_cfg.get("DRIVER", "{ODBC Driver 18 for SQL Server}")).strip()
        server = str(his_cfg.get("SERVER", "")).strip()
        port = str(his_cfg.get("PORT", "")).strip()
        database = str(his_cfg.get("DATABASE", "")).strip()
        uid = str(his_cfg.get("UID", "")).strip()
        pwd = str(his_cfg.get("PWD", "")).strip()
        trust_cert = str(his_cfg.get("TRUST_SERVER_CERTIFICATE", "yes")).strip()
        timeout = int(his_cfg.get("TIMEOUT", 30))

        server_part = f"{server},{port}" if port else server
        conn_str = (
            f"DRIVER={driver};"
            f"SERVER={server_part};"
            f"DATABASE={database};"
            f"UID={uid};"
            f"PWD={pwd};"
            f"TrustServerCertificate={trust_cert};"
        )
        self.conn = pyodbc.connect(conn_str, timeout=timeout)

    def _fetch_dicts(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, *params)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cursor.close()

    def _fetch_dicts_for_codes(
        self,
        *,
        base_query_prefix: str,
        code_field: str,
        codes: list[str],
    ) -> list[dict[str, Any]]:
        normalized_codes = list(dict.fromkeys(code for code in codes if code))
        if not normalized_codes:
            return []

        rows: list[dict[str, Any]] = []
        batch_size = self.IN_CLAUSE_BATCH_SIZE
        for start in range(0, len(normalized_codes), batch_size):
            chunk = normalized_codes[start:start + batch_size]
            placeholders = ",".join("?" for _ in chunk)
            rows.extend(
                self._fetch_dicts(
                    f"""
                    {base_query_prefix}
                    WHERE {code_field} IN ({placeholders})
                    """,
                    tuple(chunk),
                )
            )
        return rows

    def fetch_patient_types(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.DMDoiTuongBenhNhan")

    def fetch_patients_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=500)
        return self._fetch_dicts(
            f"""
            SELECT TOP ({batch_size}) *
            FROM dbo.DMBenhNhan
            WHERE MaBenhNhanTuSinh > ?
            ORDER BY MaBenhNhanTuSinh ASC
            """,
            (last_auto_id,),
        )

    def fetch_corporate_packages(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.DMGoiKhamTheoDoan")

    def fetch_exam_records_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=300)
        return self._fetch_dicts(
            f"""
            SELECT TOP ({batch_size}) *
            FROM dbo.HoSoKhamBenhNgoaiTru
            WHERE MaHoSoTuSinh > ?
            ORDER BY MaHoSoTuSinh ASC
            """,
            (last_auto_id,),
        )

    def fetch_diagnostic_imaging_details_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=300)
        return self._fetch_dicts(
            f"""
            SELECT TOP ({batch_size}) *
            FROM dbo.PhieuChanDoanHinhAnhChiTiet
            WHERE IDChanDoanHinhAnh > ?
            ORDER BY IDChanDoanHinhAnh ASC
            """,
            (last_auto_id,),
        )

    def fetch_diagnostic_imaging_by_codes(self, *, imaging_codes: list[str]) -> list[dict[str, Any]]:
        return self._fetch_dicts_for_codes(
            base_query_prefix="""
            SELECT *
            FROM dbo.PhieuChanDoanHinhAnh
            """,
            code_field="MaChanDoanHinhAnh",
            codes=imaging_codes,
        )

    def fetch_service_catalog(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.DMDichVuChiTiet")

    def fetch_package_services(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.DanhSachDichVuDinhNghiaTruocKhamTheoGoi")

    def fetch_functional_tests(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.PhieuThamDoChucNang ORDER BY MaThamDoChucNang ASC")

    def fetch_functional_test_items_by_codes(self, *, ft_codes: list[str]) -> list[dict[str, Any]]:
        return self._fetch_dicts_for_codes(
            base_query_prefix="SELECT * FROM dbo.PhieuThamDoChucNangChiTiet",
            code_field="MaThamDoChucNang",
            codes=ft_codes,
        )

    def fetch_exam_service_items(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.PhieuKhamBenhChiTiet ORDER BY MaKhamBenh ASC")

    def fetch_exam_headers_by_codes(self, *, exam_codes: list[str]) -> list[dict[str, Any]]:
        return self._fetch_dicts_for_codes(
            base_query_prefix="SELECT * FROM dbo.PhieuKhamBenh",
            code_field="MaKhamBenh",
            codes=exam_codes,
        )

    def fetch_appointments_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=300)
        return self._fetch_dicts(
            f"SELECT TOP ({batch_size}) * FROM dbo.DanhSachLichHen WHERE ID > ? ORDER BY ID ASC",
            (last_auto_id,),
        )

    def fetch_invoices(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.MeInvoice")

    def fetch_invoice_details(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.MeInvoiceRequestDetail")

    def fetch_patient_type_configs(self) -> list[dict[str, Any]]:
        return self._fetch_dicts("SELECT * FROM dbo.CauHinhDoiTuong")

    def close(self) -> None:
        self.conn.close()


class LocalPostgresHisSourceClient:
    DB_ALIAS = "his_local_pg"

    def __init__(self):
        pg_cfg = settings.HIS_LOCAL_PG
        self.schema_name = str(pg_cfg.get("SCHEMA", "dbo")).strip() or "dbo"
        self._ensure_db_alias(pg_cfg)

    def _ensure_db_alias(self, pg_cfg: dict[str, Any]) -> None:
        if self.DB_ALIAS in connections.databases:
            return
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
        connections.databases[self.DB_ALIAS] = default_db

    @staticmethod
    def _raw_model_name(table_name: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z]+", "_", table_name)
        return f"HisDbo{cleaned}"

    def _get_model(self, table_name: str):
        model_name = self._raw_model_name(table_name)
        try:
            return apps.get_model("his_integration", model_name)
        except LookupError as exc:
            raise HisSourceError(f"Missing raw HIS model for table {table_name}") from exc

    def _get_model_or_none(self, table_name: str):
        try:
            return self._get_model(table_name)
        except HisSourceError:
            return None

    @staticmethod
    def _serialize_object(obj) -> dict[str, Any]:
        row: dict[str, Any] = {}
        for field in obj._meta.concrete_fields:
            key = field.db_column or field.name
            if field.is_relation and hasattr(field, "attname"):
                row[key] = getattr(obj, field.attname)
            else:
                row[key] = getattr(obj, field.name)
        return row

    def _fetch_queryset(self, queryset) -> list[dict[str, Any]]:
        return [self._serialize_object(obj) for obj in queryset.iterator()]

    def _qualified_table_name(self, table_name: str) -> str:
        connection = connections[self.DB_ALIAS]
        quote_name = connection.ops.quote_name
        return f"{quote_name(self.schema_name)}.{quote_name(table_name)}"

    def _fetch_raw_sql(self, query: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        with connections[self.DB_ALIAS].cursor() as cursor:
            cursor.execute(query, params or [])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _fetch_raw_sql_optional(self, query: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        try:
            return self._fetch_raw_sql(query, params)
        except (ProgrammingError, DatabaseError):
            return []

    def _fetch_all(self, table_name: str, *, order_by: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        model = self._get_model_or_none(table_name)
        if model is not None:
            queryset = model.objects.using(self.DB_ALIAS).all()
            if order_by:
                queryset = queryset.order_by(*order_by)
            return self._fetch_queryset(queryset)

        order_clause = f" ORDER BY {', '.join(order_by)}" if order_by else ""
        return self._fetch_raw_sql(
            f"SELECT * FROM {self._qualified_table_name(table_name)}{order_clause}"
        )

    def _fetch_all_optional(self, table_name: str, *, order_by: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        model = self._get_model_or_none(table_name)
        if model is not None:
            queryset = model.objects.using(self.DB_ALIAS).all()
            if order_by:
                queryset = queryset.order_by(*order_by)
            return self._fetch_queryset(queryset)

        order_clause = f" ORDER BY {', '.join(order_by)}" if order_by else ""
        return self._fetch_raw_sql_optional(
            f"SELECT * FROM {self._qualified_table_name(table_name)}{order_clause}"
        )

    def fetch_patient_types(self) -> list[dict[str, Any]]:
        return self._fetch_all("DMDoiTuongBenhNhan")

    def fetch_patients_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=500)
        model = self._get_model_or_none("DMBenhNhan")
        if model is not None:
            queryset = (
                model.objects.using(self.DB_ALIAS)
                .filter(MaBenhNhanTuSinh__gt=last_auto_id)
                .order_by("MaBenhNhanTuSinh")[:batch_size]
            )
            return self._fetch_queryset(queryset)
        return self._fetch_raw_sql(
            f"""
            SELECT *
            FROM {self._qualified_table_name("DMBenhNhan")}
            WHERE "MaBenhNhanTuSinh" > %s
            ORDER BY "MaBenhNhanTuSinh" ASC
            LIMIT %s
            """,
            [last_auto_id, batch_size],
        )

    def fetch_corporate_packages(self) -> list[dict[str, Any]]:
        return self._fetch_all("DMGoiKhamTheoDoan")

    def fetch_exam_records_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=300)
        model = self._get_model_or_none("HoSoKhamBenhNgoaiTru")
        if model is not None:
            queryset = (
                model.objects.using(self.DB_ALIAS)
                .filter(MaHoSoTuSinh__gt=last_auto_id)
                .order_by("MaHoSoTuSinh")[:batch_size]
            )
            return self._fetch_queryset(queryset)
        return self._fetch_raw_sql(
            f"""
            SELECT *
            FROM {self._qualified_table_name("HoSoKhamBenhNgoaiTru")}
            WHERE "MaHoSoTuSinh" > %s
            ORDER BY "MaHoSoTuSinh" ASC
            LIMIT %s
            """,
            [last_auto_id, batch_size],
        )

    def fetch_diagnostic_imaging_details_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=300)
        model = self._get_model_or_none("PhieuChanDoanHinhAnhChiTiet")
        if model is not None:
            queryset = (
                model.objects.using(self.DB_ALIAS)
                .filter(IDChanDoanHinhAnh__gt=last_auto_id)
                .order_by("IDChanDoanHinhAnh")[:batch_size]
            )
            return self._fetch_queryset(queryset)
        return self._fetch_raw_sql(
            f"""
            SELECT *
            FROM {self._qualified_table_name("PhieuChanDoanHinhAnhChiTiet")}
            WHERE "IDChanDoanHinhAnh" > %s
            ORDER BY "IDChanDoanHinhAnh" ASC
            LIMIT %s
            """,
            [last_auto_id, batch_size],
        )

    def fetch_diagnostic_imaging_by_codes(self, *, imaging_codes: list[str]) -> list[dict[str, Any]]:
        codes = [code for code in imaging_codes if code]
        if not codes:
            return []
        model = self._get_model_or_none("PhieuChanDoanHinhAnh")
        if model is not None:
            queryset = (
                model.objects.using(self.DB_ALIAS)
                .filter(MaChanDoanHinhAnh__in=codes)
            )
            return self._fetch_queryset(queryset)
        placeholders = ", ".join(["%s"] * len(codes))
        return self._fetch_raw_sql(
            f"""
            SELECT *
            FROM {self._qualified_table_name("PhieuChanDoanHinhAnh")}
            WHERE "MaChanDoanHinhAnh" IN ({placeholders})
            """,
            codes,
        )

    def fetch_service_catalog(self) -> list[dict[str, Any]]:
        return self._fetch_all("DMDichVuChiTiet")

    def fetch_package_services(self) -> list[dict[str, Any]]:
        return self._fetch_all("DanhSachDichVuDinhNghiaTruocKhamTheoGoi")

    def fetch_functional_tests(self) -> list[dict[str, Any]]:
        return self._fetch_all("PhieuThamDoChucNang", order_by=("MaThamDoChucNang",))

    def fetch_functional_test_items_by_codes(self, *, ft_codes: list[str]) -> list[dict[str, Any]]:
        codes = [c for c in ft_codes if c]
        if not codes:
            return []
        model = self._get_model_or_none("PhieuThamDoChucNangChiTiet")
        if model is not None:
            queryset = (
                model.objects.using(self.DB_ALIAS)
                .filter(MaThamDoChucNang__in=codes)
            )
            return self._fetch_queryset(queryset)
        placeholders = ", ".join(["%s"] * len(codes))
        return self._fetch_raw_sql(
            f"""
            SELECT *
            FROM {self._qualified_table_name("PhieuThamDoChucNangChiTiet")}
            WHERE "MaThamDoChucNang" IN ({placeholders})
            """,
            codes,
        )

    def fetch_exam_service_items(self) -> list[dict[str, Any]]:
        return self._fetch_all("PhieuKhamBenhChiTiet", order_by=("MaKhamBenh",))

    def fetch_exam_headers_by_codes(self, *, exam_codes: list[str]) -> list[dict[str, Any]]:
        codes = [code for code in exam_codes if code]
        if not codes:
            return []

        model = self._get_model_or_none("PhieuKhamBenh")
        if model is not None:
            queryset = model.objects.using(self.DB_ALIAS).filter(MaKhamBenh__in=codes)
            return self._fetch_queryset(queryset)

        placeholders = ", ".join(["%s"] * len(codes))
        return self._fetch_raw_sql_optional(
            f"""
            SELECT *
            FROM {self._qualified_table_name("PhieuKhamBenh")}
            WHERE "MaKhamBenh" IN ({placeholders})
            """,
            codes,
        )

    def fetch_appointments_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=300)
        model = self._get_model_or_none("DanhSachLichHen")
        if model is not None:
            queryset = (
                model.objects.using(self.DB_ALIAS)
                .filter(ID__gt=last_auto_id)
                .order_by("ID")[:batch_size]
            )
            return self._fetch_queryset(queryset)
        return self._fetch_raw_sql_optional(
            f"""
            SELECT *
            FROM {self._qualified_table_name("DanhSachLichHen")}
            WHERE "ID" > %s
            ORDER BY "ID" ASC
            LIMIT %s
            """,
            [last_auto_id, batch_size],
        )

    def fetch_invoices(self) -> list[dict[str, Any]]:
        return self._fetch_all_optional("MeInvoice")

    def fetch_invoice_details(self) -> list[dict[str, Any]]:
        return self._fetch_all_optional("MeInvoiceRequestDetail")

    def fetch_patient_type_configs(self) -> list[dict[str, Any]]:
        return self._fetch_all_optional("CauHinhDoiTuong")

    def close(self) -> None:
        connections[self.DB_ALIAS].close()
