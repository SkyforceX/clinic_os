from __future__ import annotations

from typing import Any

from django.conf import settings


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

    def close(self) -> None:
        self.conn.close()


class LocalPostgresHisSourceClient:
    def __init__(self):
        try:
            import psycopg
            from psycopg import sql
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise HisSourceError("Missing psycopg for local PostgreSQL HIS sync") from exc

        pg_cfg = settings.HIS_LOCAL_PG
        self.schema_name = str(pg_cfg.get("SCHEMA", "dbo")).strip() or "dbo"
        conninfo = (
            f"host='{self._quote(str(pg_cfg.get('HOST', '127.0.0.1')))}' "
            f"port='{int(pg_cfg.get('PORT', 5432))}' "
            f"user='{self._quote(str(pg_cfg.get('USER', 'postgres')))}' "
            f"password='{self._quote(str(pg_cfg.get('PASSWORD', 'postgres')))}' "
            f"dbname='{self._quote(str(pg_cfg.get('NAME', 'PK_HCM')))}'"
        )
        self.sql = sql
        self.conn = psycopg.connect(conninfo, row_factory=dict_row)

    @staticmethod
    def _quote(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _table(self, table_name: str):
        return self.sql.SQL("{}.{}").format(
            self.sql.Identifier(self.schema_name),
            self.sql.Identifier(table_name),
        )

    def _fetch_all(self, table_name: str) -> list[dict[str, Any]]:
        query = self.sql.SQL("SELECT * FROM {}").format(self._table(table_name))
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            return list(cursor.fetchall())

    def fetch_patient_types(self) -> list[dict[str, Any]]:
        return self._fetch_all("DMDoiTuongBenhNhan")

    def fetch_patients_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=500)
        query = self.sql.SQL(
            """
            SELECT *
            FROM {}
            WHERE {} > %s
            ORDER BY {} ASC
            LIMIT %s
            """
        ).format(
            self._table("DMBenhNhan"),
            self.sql.Identifier("MaBenhNhanTuSinh"),
            self.sql.Identifier("MaBenhNhanTuSinh"),
        )
        with self.conn.cursor() as cursor:
            cursor.execute(query, (last_auto_id, batch_size))
            return list(cursor.fetchall())

    def fetch_corporate_packages(self) -> list[dict[str, Any]]:
        return self._fetch_all("DMGoiKhamTheoDoan")

    def fetch_exam_records_batch(self, *, last_auto_id: int, batch_size: int) -> list[dict[str, Any]]:
        batch_size = normalize_batch_size(batch_size, default=300)
        query = self.sql.SQL(
            """
            SELECT *
            FROM {}
            WHERE {} > %s
            ORDER BY {} ASC
            LIMIT %s
            """
        ).format(
            self._table("HoSoKhamBenhNgoaiTru"),
            self.sql.Identifier("MaHoSoTuSinh"),
            self.sql.Identifier("MaHoSoTuSinh"),
        )
        with self.conn.cursor() as cursor:
            cursor.execute(query, (last_auto_id, batch_size))
            return list(cursor.fetchall())

    def close(self) -> None:
        self.conn.close()
