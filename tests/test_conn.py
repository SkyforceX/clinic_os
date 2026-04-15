import pyodbc

SERVER = "172.39.39.116"   # IP server DB
PORT = 1433
DATABASE = "ARB_VIETMEDI"
USERNAME = "his"
PASSWORD = "s@123456"

import pyodbc

try:
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={SERVER},{PORT};"
        f"DATABASE={DATABASE};"
        f"UID={USERNAME};"
        f"PWD={PASSWORD};"
        "TrustServerCertificate=yes;",
        timeout=5
    )

    cursor = conn.cursor()
    cursor.execute("SELECT @@SERVERNAME")

    print("Server:", cursor.fetchone()[0])
    print("✅ OK")

    # Truy vấn danh sách bảng trong cơ sở dữ liệu
    cursor.execute("""
    SELECT 
        s.name AS schema_name,
        t.name AS table_name
    FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    ORDER BY s.name, t.name
    """)

    for row in cursor.fetchall():
        print(f"{row.schema_name}.{row.table_name}")

    # Truy vấn thông tin cột của các bảng quan trọng
    tables = [
        "DMPhongKham",
        "DmBenh",
        "HoSoCaNhan",
        "HoSoKCB",
        "ThuChi"
    ]

    # for table in tables:
    #     print(f"\n===== dbo.{table} =====")

    #     cursor.execute(f"""
    #     SELECT 
    #         c.COLUMN_NAME,
    #         c.DATA_TYPE,
    #         c.CHARACTER_MAXIMUM_LENGTH,
    #         c.IS_NULLABLE,
    #         CASE 
    #             WHEN k.COLUMN_NAME IS NOT NULL THEN 'PK'
    #             ELSE ''
    #         END AS KEY_TYPE
    #     FROM INFORMATION_SCHEMA.COLUMNS c
    #     LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
    #         ON c.TABLE_NAME = k.TABLE_NAME
    #         AND c.COLUMN_NAME = k.COLUMN_NAME
    #     WHERE c.TABLE_SCHEMA = 'dbo' 
    #     AND c.TABLE_NAME = '{table}'
    #     ORDER BY c.ORDINAL_POSITION
    #     """)

        # for row in cursor.fetchall():
        #     print(f"{row.COLUMN_NAME} | {row.DATA_TYPE} | {row.KEY_TYPE}")
            
    cursor.execute("SELECT COUNT(*) FROM dbo.HoSoKhamBenhNgoaiTru")
    print(cursor.fetchone()[0])

except Exception as e:
    print("❌ Lỗi:", e)