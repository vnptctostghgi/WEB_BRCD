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
from fastapi.responses import HTMLResponse, RedirectResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from openpyxl.cell import WriteOnlyCell


load_dotenv()

app = FastAPI(title="API trung gian VNPT CTO")


EXCEL_MAX_ROWS_PER_SHEET = 1_048_576
GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


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
    info = json.loads(raw_json)
    validate_service_account_info(info)
    return info


def validate_service_account_info(info: dict[str, Any]) -> None:
    if not isinstance(info, dict):
        raise RuntimeError("File Google Drive service account khong phai JSON object.")
    if info.get("type") != "service_account":
        raise RuntimeError("File JSON Google Drive khong phai service account key. Hay tai dung key JSON cua Service Account.")
    required = ["client_email", "private_key", "token_uri"]
    missing = [key for key in required if not str(info.get(key) or "").strip()]
    if missing:
        raise RuntimeError(f"Service account JSON thieu: {', '.join(missing)}.")
    if "BEGIN PRIVATE KEY" not in str(info.get("private_key") or ""):
        raise RuntimeError("Service account JSON co private_key khong hop le.")


def google_drive_auth_mode() -> str:
    configured = os.getenv("GOOGLE_DRIVE_AUTH_MODE", "").strip().lower()
    if configured in {"oauth", "user", "user_oauth"}:
        return "oauth"
    if configured in {"service_account", "service-account", "sa"}:
        return "service_account"
    token_file = google_drive_oauth_token_file()
    if token_file.exists():
        return "oauth"
    return "service_account"


def google_drive_oauth_client_file() -> Path:
    return Path(os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_FILE", "drive-oauth-client.json")).expanduser()


def google_drive_oauth_token_file() -> Path:
    return Path(os.getenv("GOOGLE_DRIVE_OAUTH_TOKEN_FILE", "drive-oauth-token.json")).expanduser()


def google_drive_oauth_state_file() -> Path:
    configured = os.getenv("GOOGLE_DRIVE_OAUTH_STATE_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return google_drive_oauth_token_file().with_suffix(".state.json")


def google_drive_oauth_redirect_uri() -> str:
    return os.getenv("GOOGLE_DRIVE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/drive-oauth/callback").strip()


def save_oauth_state(state: str, code_verifier: str) -> None:
    state_file = google_drive_oauth_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "state": state,
                "code_verifier": code_verifier,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_oauth_state(state: str) -> dict[str, Any]:
    state_file = google_drive_oauth_state_file()
    if not state_file.exists():
        raise RuntimeError("Khong tim thay OAuth state tren may tram. Hay mo lai /drive-oauth/start.")
    data = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("OAuth state tren may tram khong hop le. Hay mo lai /drive-oauth/start.")
    if state and data.get("state") != state:
        raise RuntimeError("OAuth state khong khop. Hay mo lai /drive-oauth/start.")
    if not str(data.get("code_verifier") or "").strip():
        raise RuntimeError("OAuth state thieu code_verifier. Hay mo lai /drive-oauth/start.")
    return data


def load_oauth_credentials() -> Credentials:
    token_file = google_drive_oauth_token_file()
    if not token_file.exists():
        raise RuntimeError("Chua ket noi Google Drive OAuth. Mo http://127.0.0.1:8000/drive-oauth/start tren may tram de cap quyen.")
    credentials = Credentials.from_authorized_user_file(str(token_file), GOOGLE_DRIVE_SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(GoogleAuthRequest())
        token_file.write_text(credentials.to_json(), encoding="utf-8")
    if not credentials.valid:
        raise RuntimeError("Token Google Drive OAuth khong hop le. Mo lai http://127.0.0.1:8000/drive-oauth/start de cap quyen lai.")
    return credentials


def service_account_drive_client() -> tuple[Any, dict[str, Any]]:
    info = load_service_account_info()
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=GOOGLE_DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False), {
        **info,
        "auth_mode": "service_account",
    }


def oauth_drive_client() -> tuple[Any, dict[str, Any]]:
    credentials = load_oauth_credentials()
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    user_email = ""
    try:
        about = drive.about().get(fields="user").execute()
        user = about.get("user") if isinstance(about.get("user"), dict) else {}
        user_email = str(user.get("emailAddress") or "")
    except Exception:
        user_email = ""
    return drive, {
        "auth_mode": "oauth",
        "user_email": user_email,
    }


def service_account_quota_message() -> str:
    return (
        "Google Drive dang dung Service Account nhung thu muc dich khong nam trong Shared Drive. "
        "Service Account khong co dung luong luu tru rieng nen khong the upload vao My Drive/thu muc Drive thuong. "
        "Hay tao Google Shared Drive, them client_email cua service account lam Content manager/Manager, "
        "tao thu muc trong Shared Drive do va cap nhat GOOGLE_DRIVE_FOLDER_ID bang ID thu muc moi."
    )


def is_service_account_quota_error(error: Exception) -> bool:
    detail = str(error).lower()
    return "service accounts do not have storage quota" in detail or "storagequotaexceeded" in detail


def drive_folder(drive: Any, folder_id: str) -> dict[str, Any]:
    if not folder_id:
        raise RuntimeError("Chua cau hinh GOOGLE_DRIVE_FOLDER_ID.")
    folder = drive.files().get(
        fileId=folder_id,
        fields="id,name,mimeType,driveId",
        supportsAllDrives=True,
    ).execute()
    if folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID khong phai ID cua thu muc Google Drive.")
    return folder


def ensure_shared_drive_folder(folder: dict[str, Any]) -> None:
    if not str(folder.get("driveId") or "").strip():
        raise RuntimeError(service_account_quota_message())


def upload_to_drive(local_path: Path, file_name: str, folder_id: str) -> dict[str, Any]:
    drive, info = drive_client()
    folder = drive_folder(drive, folder_id)
    if info.get("auth_mode") == "service_account":
        ensure_shared_drive_folder(folder)
    media = MediaFileUpload(
        str(local_path),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=True,
    )
    try:
        uploaded = drive.files().create(
            body={"name": file_name, "parents": [folder_id]},
            media_body=media,
            fields="id,name,webViewLink,webContentLink",
            supportsAllDrives=True,
        ).execute()
    except Exception as error:
        if is_service_account_quota_error(error):
            raise RuntimeError(service_account_quota_message()) from error
        raise
    return {
        "file_id": uploaded.get("id") or "",
        "file_name": uploaded.get("name") or file_name,
        "web_view_link": uploaded.get("webViewLink") or "",
        "web_content_link": uploaded.get("webContentLink") or "",
        "drive_id": folder.get("driveId") or "",
        "folder_name": folder.get("name") or "",
        "auth_mode": info.get("auth_mode") or "",
    }


def drive_client():
    if google_drive_auth_mode() == "oauth":
        return oauth_drive_client()
    return service_account_drive_client()


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
    try:
        missing = [key for key in ["DB_HOST", "DB_SERVICE", "DB_USER", "DB_PASS"] if not os.getenv(key)]
        if missing:
            return {
                "status": "error",
                "message": f"Thieu bien moi truong Oracle: {', '.join(missing)}",
            }
        with oracle_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT SYSDATE FROM DUAL")
                row = cursor.fetchone()
        return {"status": "ok", "oracle_time": str(row[0])}
    except Exception as error:
        return {
            "status": "error",
            "message": f"{type(error).__name__}: {error}",
        }


@app.get("/test-drive")
def test_drive():
    try:
        drive, info = drive_client()
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
        folder: dict[str, Any] = {}
        if folder_id:
            folder = drive_folder(drive, folder_id)
            if info.get("auth_mode") == "service_account" and not folder.get("driveId"):
                return {
                    "status": "error",
                    "message": service_account_quota_message(),
                    "auth_mode": info.get("auth_mode") or "",
                    "client_email": info.get("client_email") or "",
                    "folder_id": folder_id,
                    "folder_name": folder.get("name") or "",
                    "drive_type": "my_drive",
                }
        return {
            "status": "ok",
            "auth_mode": info.get("auth_mode") or "",
            "client_email": info.get("client_email") or "",
            "user_email": info.get("user_email") or "",
            "folder_id": folder_id,
            "folder_name": folder.get("name") or "",
            "drive_id": folder.get("driveId") or "",
            "drive_type": "shared_drive" if folder.get("driveId") else ("my_drive" if folder_id else ""),
        }
    except Exception as error:
        return {
            "status": "error",
            "message": f"{type(error).__name__}: {error}",
        }


@app.get("/drive-oauth/start")
def drive_oauth_start():
    try:
        try:
            from google_auth_oauthlib.flow import Flow
        except ModuleNotFoundError as error:
            raise RuntimeError("Chua cai google-auth-oauthlib. Hay chay: python -m pip install google-auth-oauthlib") from error

        client_file = google_drive_oauth_client_file()
        if not client_file.exists():
            raise RuntimeError(f"Khong tim thay OAuth client JSON: {client_file}")

        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        flow = Flow.from_client_secrets_file(
            str(client_file),
            scopes=GOOGLE_DRIVE_SCOPES,
            redirect_uri=google_drive_oauth_redirect_uri(),
            autogenerate_code_verifier=True,
        )
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        save_oauth_state(state, str(flow.code_verifier or ""))
        return RedirectResponse(authorization_url)
    except Exception as error:
        return HTMLResponse(f"<h3>Khong mo duoc OAuth Google Drive</h3><pre>{type(error).__name__}: {error}</pre>", status_code=500)


@app.get("/drive-oauth/callback")
def drive_oauth_callback(code: str = "", state: str = "", error: str = ""):
    try:
        if error:
            raise RuntimeError(f"Google tu choi cap quyen: {error}")
        if not code:
            raise RuntimeError("Google callback thieu code.")
        try:
            from google_auth_oauthlib.flow import Flow
        except ModuleNotFoundError as module_error:
            raise RuntimeError("Chua cai google-auth-oauthlib. Hay chay: python -m pip install google-auth-oauthlib") from module_error

        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        oauth_state = load_oauth_state(state)
        flow = Flow.from_client_secrets_file(
            str(google_drive_oauth_client_file()),
            scopes=GOOGLE_DRIVE_SCOPES,
            redirect_uri=google_drive_oauth_redirect_uri(),
            state=state or oauth_state.get("state"),
            code_verifier=str(oauth_state.get("code_verifier") or ""),
            autogenerate_code_verifier=False,
        )
        flow.fetch_token(code=code)
        token_file = google_drive_oauth_token_file()
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(flow.credentials.to_json(), encoding="utf-8")
        google_drive_oauth_state_file().unlink(missing_ok=True)
        return HTMLResponse(
            "<h3>Da ket noi Google Drive OAuth thanh cong.</h3>"
            "<p>Co the dong cua so nay, sau do chay lai /test-drive va xuat file tren web.</p>"
        )
    except Exception as callback_error:
        return HTMLResponse(f"<h3>Ket noi OAuth Google Drive loi</h3><pre>{type(callback_error).__name__}: {callback_error}</pre>", status_code=500)


@app.post("/api/du-lieu-web")
def du_lieu_web(payload: dict[str, Any], authorization: str = Header(default="")):
    try:
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
            folder_id = str(os.getenv("GOOGLE_DRIVE_FOLDER_ID") or payload.get("drive_folder_id") or "").strip()
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
    except HTTPException:
        raise
    except Exception as error:
        return {
            "ok": False,
            "status": "error",
            "message": f"{type(error).__name__}: {error}",
        }
