from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import oracledb
import openpyxl
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from openpyxl.cell import WriteOnlyCell


load_dotenv()

app = FastAPI(title="API trung gian VNPT CTO")


EXCEL_MAX_ROWS_PER_SHEET = 1_048_576


def require_token(authorization: str = "") -> None:
    token = os.getenv("API_TOKEN", "").strip()
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="API token khong hop le.")


def oracle_dsn() -> str:
    return oracledb.makedsn(
        os.getenv("DB_HOST"),
        int(os.getenv("DB_PORT", "1521")),
        service_name=os.getenv("DB_SERVICE"),
    )


def oracle_connect():
    return oracledb.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        dsn=oracle_dsn(),
    )


def clean_sql(sql: str) -> str:
    value = str(sql or "").strip()
    while value.endswith(";"):
        value = value[:-1].strip()
    return value


def safe_file_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return name.strip("._") or f"truy_van_sql_{datetime.now():%Y%m%d_%H%M%S}.xlsx"


def excel_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, datetime, date)):
        return value
    return str(value)


def load_service_account_info() -> dict[str, Any]:
    raw_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    raw_base64 = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
    file_path = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", "").strip()
    if raw_base64:
        raw_json = base64.b64decode(raw_base64).decode("utf-8")
    elif file_path:
        raw_json = Path(file_path).read_text(encoding="utf-8")
    if not raw_json:
        raise RuntimeError("Chua cau hinh Google Drive service account tren may tram.")
    return json.loads(raw_json)


def upload_to_drive(local_path: Path, file_name: str, folder_id: str) -> dict[str, Any]:
    info = load_service_account_info()
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    media = MediaFileUpload(
        str(local_path),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=True,
    )
    uploaded = drive.files().create(
        body={"name": file_name, "parents": [folder_id]},
        media_body=media,
        fields="id,name,webViewLink,webContentLink",
        supportsAllDrives=True,
    ).execute()
    return {
        "file_id": uploaded.get("id") or "",
        "file_name": uploaded.get("name") or file_name,
        "web_view_link": uploaded.get("webViewLink") or "",
        "web_content_link": uploaded.get("webContentLink") or "",
    }


def count_rows(cursor, sql: str, binds: dict[str, Any]) -> int:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM ({sql}) Q", binds)
        row = cursor.fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def fetch_page(cursor, sql: str, binds: dict[str, Any], page: int, page_size: int) -> tuple[list[str], list[dict[str, Any]]]:
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(int(page_size or 20), 20000))
    offset = (safe_page - 1) * safe_page_size
    paged_sql = f"""
SELECT *
FROM ({sql}) Q
OFFSET :PAGING_OFFSET ROWS FETCH NEXT :PAGING_LIMIT ROWS ONLY
"""
    cursor.execute(
        paged_sql,
        {**binds, "PAGING_OFFSET": offset, "PAGING_LIMIT": safe_page_size},
    )
    columns = [item[0] for item in (cursor.description or [])]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return columns, rows


def write_export_to_excel(cursor, sql: str, binds: dict[str, Any], target_path: Path, page_size: int, max_rows: int) -> dict[str, Any]:
    workbook = openpyxl.Workbook(write_only=True)
    sheet = None
    sheet_index = 0
    sheet_rows = 0
    total_written = 0
    total = count_rows(cursor, sql, binds)
    page = 1
    columns: list[str] = []

    def start_sheet() -> Any:
        nonlocal sheet_index, sheet_rows
        sheet_index += 1
        title = "TruyVanSQL" if sheet_index == 1 else f"TruyVanSQL_{sheet_index}"
        ws = workbook.create_sheet(title[:31])
        sheet_rows = 0
        return ws

    while total_written < max_rows:
        page_columns, rows = fetch_page(cursor, sql, binds, page, page_size)
        if not columns:
            columns = page_columns or ["Ket qua"]
        if not rows:
            break
        if sheet is None:
            sheet = start_sheet()
            sheet.append([WriteOnlyCell(sheet, value=column) for column in columns])
            sheet_rows = 1
        for row in rows:
            if total_written >= max_rows:
                break
            if sheet_rows >= EXCEL_MAX_ROWS_PER_SHEET:
                sheet = start_sheet()
                sheet.append([WriteOnlyCell(sheet, value=column) for column in columns])
                sheet_rows = 1
            sheet.append([excel_value(row.get(column)) for column in columns])
            sheet_rows += 1
            total_written += 1
        if total and total_written >= total:
            break
        if len(rows) < page_size:
            break
        page += 1

    if sheet is None:
        sheet = start_sheet()
        sheet.append(columns or ["Ket qua"])
    workbook.save(target_path)
    return {"rows": total_written, "total": total or total_written, "columns": columns}


@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/test-oracle")
def test_oracle():
    with oracle_connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT SYSDATE FROM DUAL")
            row = cursor.fetchone()
    return {"status": "ok", "oracle_time": str(row[0])}


@app.post("/api/du-lieu-web")
def du_lieu_web(payload: dict[str, Any], authorization: str = Header(default="")):
    require_token(authorization)
    action = str(payload.get("action") or "").strip()
    if action == "health_check":
        return {"ok": True, "status": "ok"}

    sql = clean_sql(payload.get("cau_lenh_sql") or "")
    binds = payload.get("tham_so") if isinstance(payload.get("tham_so"), dict) else {}
    if not sql:
        raise HTTPException(status_code=400, detail="Thieu cau_lenh_sql.")

    if action == "run_sql_report":
        pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
        page = int(pagination.get("page") or 1)
        page_size = int(pagination.get("page_size") or 20)
        with oracle_connect() as conn:
            with conn.cursor() as cursor:
                total = count_rows(cursor, sql, binds)
                columns, rows = fetch_page(cursor, sql, binds, page, page_size)
        return {
            "ok": True,
            "columns": columns,
            "rows": rows,
            "total": total or len(rows),
            "page": page,
            "page_size": page_size,
        }

    if action == "export_sql_report_to_drive":
        folder_id = str(payload.get("drive_folder_id") or os.getenv("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
        if not folder_id:
            raise HTTPException(status_code=400, detail="Thieu drive_folder_id.")
        pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
        page_size = int(pagination.get("page_size") or os.getenv("EXPORT_PAGE_SIZE", "5000"))
        max_rows = int(pagination.get("max_rows") or os.getenv("EXPORT_MAX_ROWS", "1000000"))
        file_name = safe_file_name(payload.get("file_name") or f"{payload.get('ma_bao_cao')}_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
        export_dir = Path(os.getenv("EXPORT_DIR", str(Path(tempfile.gettempdir()) / "vnptcto_exports")))
        export_dir.mkdir(parents=True, exist_ok=True)
        target_path = export_dir / file_name
        with oracle_connect() as conn:
            with conn.cursor() as cursor:
                result = write_export_to_excel(cursor, sql, binds, target_path, page_size, max_rows)
        uploaded = upload_to_drive(target_path, file_name, folder_id)
        return {
            "ok": True,
            "status": "uploaded_google_drive",
            "message": "Da xuat Excel tren may tram va upload Google Drive.",
            "file_id": uploaded.get("file_id") or "",
            "file_name": uploaded.get("file_name") or file_name,
            "drive_url": uploaded.get("web_view_link") or uploaded.get("web_content_link") or "",
            "storage_link": uploaded.get("web_view_link") or uploaded.get("web_content_link") or "",
            "rows": result["rows"],
            "total": result["total"],
            "columns": result["columns"],
        }

    raise HTTPException(status_code=400, detail=f"Action khong ho tro: {action}")
