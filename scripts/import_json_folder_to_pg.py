#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import toàn bộ file JSON trong một thư mục vào PostgreSQL local.

Mục tiêu:
- Tạo database PK_HCM (mặc định)
- Tạo schema dbo (mặc định)
- Mỗi file JSON => 1 bảng
- Tên bảng lấy từ tên file:
    dbo.DMBenhNhan.json   -> schema dbo, table DMBenhNhan
    DMBenhNhan.json       -> schema dbo, table DMBenhNhan
    custom.table.json     -> schema custom, table table
- Tự suy luận cột từ toàn bộ JSON object trong file
- Tự tạo bảng và nạp toàn bộ dữ liệu

Khuyến nghị đặt tên file đúng tên bảng production, ví dụ:
    data_mau/
      dbo.DMBenhNhan.json
      dbo.hosokhambenhngoaitru.json
      dbo.DMGoiKhamTheoDoan.json

Ví dụ chạy:
    python import_json_folder_to_pg.py \
        --data-dir ./data_mau \
        --host 127.0.0.1 \
        --port 5432 \
        --user postgres \
        --password postgres \
        --db-name PK_HCM

Cài thư viện:
    pip install psycopg[binary]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import psycopg
    from psycopg import sql
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Thiếu thư viện psycopg. Cài bằng lệnh: pip install psycopg[binary]"
    ) from exc


@dataclass
class TableTarget:
    schema_name: str
    table_name: str


JSON_SCALAR = (str, int, float, bool, type(None))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Đọc folder JSON và import vào PostgreSQL"
    )
    parser.add_argument("--data-dir", required=True, help="Thư mục chứa file JSON")
    parser.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", "postgres"))
    parser.add_argument(
        "--maintenance-db",
        default=os.getenv("PGMAINTENANCE_DB", "postgres"),
        help="DB dùng để login và tạo database mới",
    )
    parser.add_argument(
        "--db-name",
        default=os.getenv("PGDATABASE", "PK_HCM"),
        help="Tên database đích cần tạo/import",
    )
    parser.add_argument(
        "--default-schema",
        default="dbo",
        help="Schema mặc định nếu tên file không chứa prefix schema",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Encoding đọc file JSON, mặc định utf-8-sig",
    )
    parser.add_argument(
        "--drop-existing-tables",
        action="store_true",
        help="Nếu bật thì DROP TABLE trước khi tạo lại",
    )
    parser.add_argument(
        "--truncate-existing-tables",
        action="store_true",
        help="Nếu bật thì TRUNCATE trước khi insert nếu bảng đã tồn tại",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Số dòng insert mỗi đợt",
    )
    parser.add_argument(
        "--file-pattern",
        default="*.json",
        help="Pattern file JSON, mặc định *.json",
    )
    parser.add_argument(
        "--name-map",
        default="",
        help=(
            "File JSON mapping tên file -> tên bảng đích. "
            "Ví dụ: {\"2234...json\": \"dbo.DMPhieuThu\"}"
        ),
    )
    parser.add_argument(
        "--keep-empty-objects",
        action="store_true",
        help="Nếu file là [] thì vẫn tạo bảng trống với 1 cột __raw_json jsonb",
    )
    return parser.parse_args()


def quote_dsn_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def build_conninfo(
    *, host: str, port: int, user: str, password: str, dbname: str
) -> str:
    return (
        f"host='{quote_dsn_value(host)}' "
        f"port='{port}' "
        f"user='{quote_dsn_value(user)}' "
        f"password='{quote_dsn_value(password)}' "
        f"dbname='{quote_dsn_value(dbname)}'"
    )


def list_json_files(data_dir: Path, pattern: str) -> list[Path]:
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục dữ liệu: {data_dir}")
    files = sorted(data_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy file nào khớp pattern '{pattern}' trong {data_dir}"
        )
    return files


def parse_target_name(target_name: str, default_schema: str) -> TableTarget:
    cleaned = target_name.strip()
    if "." in cleaned:
        schema_name, table_name = cleaned.split(".", 1)
        if schema_name and table_name:
            return TableTarget(schema_name=schema_name, table_name=table_name)
    return TableTarget(schema_name=default_schema, table_name=cleaned)


def load_name_map(name_map_path: str) -> dict[str, str]:
    if not name_map_path:
        return {}
    path = Path(name_map_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file name-map: {path}")
    with path.open("r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("name-map phải là JSON object dạng {filename: 'dbo.Table'}")
    return {str(k): str(v) for k, v in data.items()}


def resolve_target_from_filename(file_path: Path, default_schema: str, name_map: dict[str, str] | None = None) -> TableTarget:
    name_map = name_map or {}
    mapped = (
        name_map.get(file_path.name)
        or name_map.get(file_path.stem)
        or name_map.get(str(file_path))
    )
    if mapped:
        return parse_target_name(mapped, default_schema)

    return parse_target_name(file_path.stem.strip(), default_schema)


MSSQL_JSON_DATE_RE = re.compile(r"^/Date\((?P<ms>-?\d+)(?:[+-]\d+)?\)/$")
ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}(?::\d{2})?$")


def normalize_json_rows(raw: Any, file_path: Path) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(
                    f"File {file_path.name}: phần tử thứ {index} không phải object JSON"
                )
            rows.append(item)
        return rows

    if isinstance(raw, dict):
        if all(isinstance(v, dict) for v in raw.values()):
            return [v for v in raw.values()]
        return [raw]

    raise ValueError(
        f"File {file_path.name}: JSON root phải là list[object] hoặc object"
    )


def load_json_file(file_path: Path, encoding: str) -> list[dict[str, Any]]:
    with file_path.open("r", encoding=encoding) as fh:
        raw = json.load(fh)
    return normalize_json_rows(raw, file_path)


def collect_all_columns(rows: Sequence[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        for key in row.keys():
            seen.setdefault(str(key), None)
    return list(seen.keys())


def classify_string(value: str) -> str:
    if MSSQL_JSON_DATE_RE.match(value):
        return "timestamp"
    if ISO_DATETIME_RE.match(value):
        return "timestamp"
    if ISO_DATE_RE.match(value):
        return "date"
    if TIME_RE.match(value):
        return "time"
    return "text"


def infer_pg_type(values: Iterable[Any]) -> str:
    seen_kinds: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            seen_kinds.add("bool")
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            seen_kinds.add("int")
            continue
        if isinstance(value, float):
            seen_kinds.add("float")
            continue
        if isinstance(value, Decimal):
            seen_kinds.add("numeric")
            continue
        if isinstance(value, (dict, list)):
            seen_kinds.add("jsonb")
            continue
        if isinstance(value, str):
            seen_kinds.add(classify_string(value))
            continue
        seen_kinds.add("text")

    if not seen_kinds:
        return "text"
    if "jsonb" in seen_kinds:
        return "jsonb"
    if seen_kinds == {"bool"}:
        return "boolean"
    if seen_kinds <= {"int"}:
        return "bigint"
    if seen_kinds <= {"int", "float", "numeric"}:
        return "double precision"
    if seen_kinds == {"date"}:
        return "date"
    if seen_kinds == {"time"}:
        return "time"
    if seen_kinds == {"timestamp"}:
        return "timestamp"
    return "text"


def infer_column_types(rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for column in columns:
        column_values = (row.get(column) for row in rows)
        result[column] = infer_pg_type(column_values)
    return result


def convert_value(value: Any, pg_type: str) -> Any:
    if value is None:
        return None

    if pg_type == "jsonb":
        return json.dumps(value, ensure_ascii=False)

    if pg_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "t", "yes", "y"}:
                return True
            if lowered in {"0", "false", "f", "no", "n"}:
                return False
        return bool(value)

    if pg_type == "bigint":
        return int(value)

    if pg_type == "double precision":
        return float(value)

    if pg_type == "date" and isinstance(value, str):
        return date.fromisoformat(value)

    if pg_type == "time" and isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError:
            return value

    if pg_type == "timestamp" and isinstance(value, str):
        match = MSSQL_JSON_DATE_RE.match(value)
        if match:
            milliseconds = int(match.group("ms"))
            return datetime.fromtimestamp(milliseconds / 1000)
        text = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return value

    return value


def build_create_table_statement(
    schema_name: str,
    table_name: str,
    columns: Sequence[str],
    column_types: dict[str, str],
) -> sql.SQL:
    column_defs: list[sql.SQL] = []
    for column in columns:
        column_defs.append(
            sql.SQL("{} {}")
            .format(sql.Identifier(column), sql.SQL(column_types[column]))
        )

    return sql.SQL("CREATE TABLE {}.{} ({})").format(
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
        sql.SQL(", ").join(column_defs) if column_defs else sql.SQL('"__raw_json" jsonb'),
    )


def ensure_database_exists(args: argparse.Namespace) -> None:
    conninfo = build_conninfo(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.maintenance_db,
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (args.db_name,))
            exists = cur.fetchone() is not None
            if not exists:
                print(f"[DB] Tạo database {args.db_name}")
                cur.execute(
                    sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(
                        sql.Identifier(args.db_name)
                    )
                )
            else:
                print(f"[DB] Database {args.db_name} đã tồn tại")


def connect_target_db(args: argparse.Namespace) -> psycopg.Connection:
    conninfo = build_conninfo(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.db_name,
    )
    return psycopg.connect(conninfo)


def ensure_schema_exists(conn: psycopg.Connection, schema_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}")
            .format(sql.Identifier(schema_name))
        )


def table_exists(conn: psycopg.Connection, schema_name: str, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema_name, table_name),
        )
        return cur.fetchone() is not None


def prepare_table(
    conn: psycopg.Connection,
    *,
    schema_name: str,
    table_name: str,
    columns: Sequence[str],
    column_types: dict[str, str],
    drop_existing: bool,
    truncate_existing: bool,
) -> None:
    exists = table_exists(conn, schema_name, table_name)
    with conn.cursor() as cur:
        if exists and drop_existing:
            print(f"[TABLE] DROP {schema_name}.{table_name}")
            cur.execute(
                sql.SQL("DROP TABLE {}.{}")
                .format(sql.Identifier(schema_name), sql.Identifier(table_name))
            )
            exists = False

        if not exists:
            print(f"[TABLE] CREATE {schema_name}.{table_name}")
            cur.execute(
                build_create_table_statement(
                    schema_name=schema_name,
                    table_name=table_name,
                    columns=columns,
                    column_types=column_types,
                )
            )
        elif truncate_existing:
            print(f"[TABLE] TRUNCATE {schema_name}.{table_name}")
            cur.execute(
                sql.SQL("TRUNCATE TABLE {}.{}")
                .format(sql.Identifier(schema_name), sql.Identifier(table_name))
            )


def chunked(items: Sequence[Any], chunk_size: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def insert_rows(
    conn: psycopg.Connection,
    *,
    schema_name: str,
    table_name: str,
    columns: Sequence[str],
    column_types: dict[str, str],
    rows: Sequence[dict[str, Any]],
    chunk_size: int,
) -> int:
    if not rows:
        return 0

    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
    insert_sql = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        placeholders,
    )

    total_inserted = 0
    with conn.cursor() as cur:
        for batch in chunked(list(rows), chunk_size):
            batch_values = []
            for row in batch:
                batch_values.append(
                    tuple(
                        convert_value(row.get(column), column_types[column])
                        for column in columns
                    )
                )
            cur.executemany(insert_sql, batch_values)
            total_inserted += len(batch_values)
    return total_inserted


def process_file(conn: psycopg.Connection, file_path: Path, args: argparse.Namespace) -> None:
    target = resolve_target_from_filename(
        file_path,
        args.default_schema,
        getattr(args, "_name_map", {}),
    )
    rows = load_json_file(file_path, args.encoding)
    columns = collect_all_columns(rows)

    if not rows and not args.keep_empty_objects:
        print(f"[SKIP] {file_path.name}: file rỗng []")
        return

    if not columns:
        columns = ["__raw_json"]
        rows = [{"__raw_json": row} for row in rows] if rows else []

    column_types = infer_column_types(rows, columns)

    ensure_schema_exists(conn, target.schema_name)
    prepare_table(
        conn,
        schema_name=target.schema_name,
        table_name=target.table_name,
        columns=columns,
        column_types=column_types,
        drop_existing=args.drop_existing_tables,
        truncate_existing=args.truncate_existing_tables,
    )
    inserted = insert_rows(
        conn,
        schema_name=target.schema_name,
        table_name=target.table_name,
        columns=columns,
        column_types=column_types,
        rows=rows,
        chunk_size=args.chunk_size,
    )
    print(
        f"[OK] {file_path.name} -> {target.schema_name}.{target.table_name} | "
        f"columns={len(columns)} | rows={inserted}"
    )


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()
    files = list_json_files(data_dir, args.file_pattern)
    args._name_map = load_name_map(args.name_map)

    print(f"[START] data_dir={data_dir}")
    print(f"[START] files={len(files)}")
    ensure_database_exists(args)

    with connect_target_db(args) as conn:
        conn.autocommit = False
        try:
            for file_path in files:
                process_file(conn, file_path, args)
            conn.commit()
            print("[DONE] Import hoàn tất")
        except Exception as exc:
            conn.rollback()
            print(f"[ERROR] {exc}", file=sys.stderr)
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
