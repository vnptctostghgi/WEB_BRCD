from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import oracledb
import openpyxl
from dotenv import find_dotenv, load_dotenv
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
API_MIDDLEWARE_VERSION = "2026.07.29-oracle-date-binds"
ORACLE_DATE_INPUT_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%Y%m%d")
ORACLE_DSN_ENV_KEYS = (
    "DB_DSN",
    "ORACLE_DSN",
    "TNS_DSN",
    "DB_CONNECT_STRING",
    "ORACLE_CONNECT_STRING",
)
ORACLE_CLIENT_INITIALIZED = False


def require_token(authorization: str = "") -> None:
    token = os.getenv("API_TOKEN", "").strip()
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="API token khong hop le.")


def env_value(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "")
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def parse_bool_env(name: str) -> bool:
    return env_value(name).lower() in {"1", "true", "yes", "y", "on"}


def suspicious_local_oracle_dsn(dsn: str) -> bool:
    normalized = dsn.strip().lower()
    return normalized in {"/", "//", "beq", "bequeath", "local"} or normalized.startswith("beq:")


def configure_oracle_client() -> None:
    global ORACLE_CLIENT_INITIALIZED
    if ORACLE_CLIENT_INITIALIZED:
        return
    client_lib_dir = env_value("ORACLE_CLIENT_LIB_DIR")
    if client_lib_dir or parse_bool_env("ORACLE_THICK_MODE"):
        kwargs = {"lib_dir": client_lib_dir} if client_lib_dir else {}
        oracledb.init_oracle_client(**kwargs)
    ORACLE_CLIENT_INITIALIZED = True


def oracle_connection_config() -> dict[str, str]:
    user = env_value("DB_USER", "DB_USERNAME", "ORACLE_USER", "ORACLE_DB_USER")
    password = env_value("DB_PASS", "DB_PASSWORD", "ORACLE_PASSWORD", "ORACLE_DB_PASS", "ORACLE_DB_PASSWORD")
    missing_credentials = []
    if not user:
        missing_credentials.append("DB_USER")
    if not password:
        missing_credentials.append("DB_PASS")
    if missing_credentials:
        raise RuntimeError(f"Thieu bien moi truong Oracle: {', '.join(missing_credentials)}")

    dsn = env_value(*ORACLE_DSN_ENV_KEYS)
    host = env_value("DB_HOST", "ORACLE_HOST")
    port_text = env_value("DB_PORT", "ORACLE_PORT") or "1521"
    service = env_value("DB_SERVICE", "ORACLE_SERVICE", "SERVICE_NAME")
    sid = env_value("DB_SID", "ORACLE_SID")
    source = "DB_DSN"

    if dsn and suspicious_local_oracle_dsn(dsn):
        if not host or not (service or sid):
            raise RuntimeError(
                "DB_DSN dang tro toi ket noi Oracle local/bequeath. "
                "Hay cau hinh DB_DSN dang TCP hoac DB_HOST + DB_SERVICE/DB_SID tren web roi tai lai bo cai."
            )
        dsn = ""

    if not dsn:
        source = "DB_HOST/DB_SERVICE"
        missing = []
        if not host:
            missing.append("DB_HOST")
        if not service and not sid:
            missing.append("DB_SERVICE hoac DB_SID")
        if missing:
            raise RuntimeError(
                "Thieu cau hinh Oracle: "
                + ", ".join(missing)
                + ". Hay cau hinh DB co quan tren web roi tai lai bo cai may tram."
            )
        try:
            port = int(port_text)
        except ValueError as error:
            raise RuntimeError(f"DB_PORT khong hop le: {port_text}") from error
        dsn = oracledb.makedsn(host, port, service_name=service) if service else oracledb.makedsn(host, port, sid=sid)

    if not dsn.strip() or suspicious_local_oracle_dsn(dsn):
        raise RuntimeError("Cau hinh Oracle DSN khong hop le, khong duoc dung ket noi local/bequeath.")

    return {
        "user": user,
        "password": password,
        "dsn": dsn,
        "source": source,
        "host": host,
        "port": port_text,
        "service": service,
        "sid": sid,
    }


def oracle_connect():
    configure_oracle_client()
    config = oracle_connection_config()
    return oracledb.connect(
        user=config["user"],
        password=config["password"],
        dsn=config["dsn"],
    )


def config_present(*names: str) -> bool:
    return bool(env_value(*names))


def preview_value(value: str, limit: int = 90) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def clean_sql(sql: str) -> str:
    value = str(sql or "").strip()
    while value.endswith(";"):
        value = value[:-1].strip()
    return value


def parse_oracle_date_input(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ORACLE_DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def oracle_mask_to_strftime(mask: str) -> str:
    result = str(mask or "").upper()
    replacements = [
        ("HH24", "%H"),
        ("YYYY", "%Y"),
        ("RRRR", "%Y"),
        ("RR", "%y"),
        ("YY", "%y"),
        ("MM", "%m"),
        ("DD", "%d"),
        ("MI", "%M"),
        ("SS", "%S"),
    ]
    for token, replacement in replacements:
        result = result.replace(token, replacement)
    return result if "%" in result else ""


def format_oracle_date_value(value: Any, mask: str) -> Any:
    parsed = parse_oracle_date_input(value)
    formatter = oracle_mask_to_strftime(mask)
    if not parsed or not formatter:
        return value
    return parsed.strftime(formatter)


def oracle_date_mask_for_bind(sql: str, name: str) -> str:
    pattern = re.compile(
        rf"\bto_(?:date|timestamp)\s*\(\s*:{re.escape(name)}\b\s*,\s*'([^']+)'",
        re.IGNORECASE,
    )
    match = pattern.search(sql or "")
    return str(match.group(1) or "").strip() if match else ""


def normalize_binds_for_sql(sql: str, binds: dict[str, Any]) -> dict[str, Any]:
    if not binds:
        return binds
    normalized = dict(binds)
    for key, value in binds.items():
        mask = oracle_date_mask_for_bind(sql, str(key))
        if mask:
            normalized[key] = format_oracle_date_value(value, mask)
    return normalized


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
        raw_json = base64.b64decode(raw_base64).decode("utf-8-sig")
    elif file_path:
        raw_json = Path(file_path).read_text(encoding="utf-8-sig")
    if not raw_json:
        raise RuntimeError("Chua cau hinh Google Drive service account tren may tram.")
    info = json.loads(raw_json.lstrip("\ufeff"))
    validate_service_account_info(info)
    return info


def read_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig").lstrip("\ufeff"))
    if not isinstance(data, dict):
        raise RuntimeError(f"File JSON khong phai object: {path}")
    return data


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
    return "oauth"


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
    data = read_json_file(state_file)
    if state and data.get("state") != state:
        raise RuntimeError("OAuth state khong khop. Hay mo lai /drive-oauth/start.")
    if not str(data.get("code_verifier") or "").strip():
        raise RuntimeError("OAuth state thieu code_verifier. Hay mo lai /drive-oauth/start.")
    return data


def load_oauth_credentials() -> Credentials:
    token_file = google_drive_oauth_token_file()
    if not token_file.exists():
        raise RuntimeError("Chua ket noi Google Drive OAuth. Mo http://127.0.0.1:8000/drive-oauth/start tren may tram de cap quyen.")
    credentials = Credentials.from_authorized_user_info(read_json_file(token_file), GOOGLE_DRIVE_SCOPES)
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
        "Thu muc Google Drive nay la thu muc My Drive duoc share thong thuong. "
        "Service Account khong co dung luong de upload vao kieu thu muc nay. "
        "Hay dung GOOGLE_DRIVE_AUTH_MODE=oauth va cap quyen bang tai khoan Google da duoc share thu muc."
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


def upload_to_drive(local_path: Path, file_name: str, folder_id: str, mime_type: str = "") -> dict[str, Any]:
    drive, info = drive_client()
    folder = drive_folder(drive, folder_id)
    if info.get("auth_mode") == "service_account":
        ensure_shared_drive_folder(folder)
    media = MediaFileUpload(
        str(local_path),
        mimetype=mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream",
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


def payload_file_bytes(payload: dict[str, Any]) -> bytes:
    encoded = str(
        payload.get("file_base64")
        or payload.get("content_base64")
        or payload.get("data_base64")
        or ""
    ).strip()
    if "," in encoded and encoded.lower().startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    if not encoded:
        raise HTTPException(status_code=400, detail="Thieu file_base64.")
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception as error:
        raise HTTPException(status_code=400, detail="file_base64 khong hop le.") from error


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
    return {"status": "ok", "version": API_MIDDLEWARE_VERSION}


@app.get("/config-status")
def config_status():
    payload: dict[str, Any] = {
        "status": "ok",
        "version": API_MIDDLEWARE_VERSION,
        "pid": os.getpid(),
        "cwd": str(Path.cwd()),
        "app_file": str(Path(__file__).resolve()),
        "env_file": find_dotenv(usecwd=True),
        "db_dsn_configured": config_present(*ORACLE_DSN_ENV_KEYS),
        "db_host": env_value("DB_HOST", "ORACLE_HOST"),
        "db_port": env_value("DB_PORT", "ORACLE_PORT") or "1521",
        "db_service": env_value("DB_SERVICE", "ORACLE_SERVICE", "SERVICE_NAME"),
        "db_sid_configured": config_present("DB_SID", "ORACLE_SID"),
        "db_user_configured": config_present("DB_USER", "DB_USERNAME", "ORACLE_USER", "ORACLE_DB_USER"),
        "db_pass_configured": config_present("DB_PASS", "DB_PASSWORD", "ORACLE_PASSWORD", "ORACLE_DB_PASS", "ORACLE_DB_PASSWORD"),
        "drive_folder_configured": config_present("GOOGLE_DRIVE_FOLDER_ID"),
        "drive_auth_mode": google_drive_auth_mode(),
    }
    try:
        config = oracle_connection_config()
        payload.update(
            {
                "oracle_config_ok": True,
                "dsn_source": config.get("source") or "",
                "dsn_preview": preview_value(config.get("dsn") or ""),
            }
        )
    except Exception as error:
        payload.update(
            {
                "oracle_config_ok": False,
                "oracle_config_error": f"{type(error).__name__}: {error}",
            }
        )
    return payload


@app.get("/test-oracle")
def test_oracle():
    try:
        config = oracle_connection_config()
        with oracle_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT SYSDATE FROM DUAL")
                row = cursor.fetchone()
        return {
            "status": "ok",
            "oracle_time": str(row[0]),
            "dsn_source": config.get("source") or "",
            "host": config.get("host") or "",
            "service": config.get("service") or "",
            "sid": config.get("sid") or "",
        }
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
        flow = Flow.from_client_config(
            read_json_file(client_file),
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
        flow = Flow.from_client_config(
            read_json_file(google_drive_oauth_client_file()),
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

        if action in {"upload_file_to_drive", "upload_onebss_file_to_drive"}:
            folder_id = str(os.getenv("GOOGLE_DRIVE_FOLDER_ID") or payload.get("drive_folder_id") or "").strip()
            if not folder_id:
                raise HTTPException(status_code=400, detail="Thieu drive_folder_id.")
            content = payload_file_bytes(payload)
            if not content:
                raise HTTPException(status_code=400, detail="File upload rong.")
            file_name = safe_file_name(payload.get("file_name") or f"onebss_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
            content_type = str(payload.get("content_type") or "").strip()
            export_dir = Path(os.getenv("EXPORT_DIR", str(Path(tempfile.gettempdir()) / "vnptcto_exports")))
            export_dir.mkdir(parents=True, exist_ok=True)
            target_path = export_dir / file_name
            target_path.write_bytes(content)
            uploaded = upload_to_drive(target_path, file_name, folder_id, content_type)
            return {
                "ok": True,
                "status": "uploaded_google_drive",
                "message": "Da upload file len Google Drive qua API trung gian.",
                "file_id": uploaded.get("file_id") or "",
                "file_name": uploaded.get("file_name") or file_name,
                "drive_url": uploaded.get("web_view_link") or uploaded.get("web_content_link") or "",
                "storage_link": uploaded.get("web_view_link") or uploaded.get("web_content_link") or "",
                "auth_mode": uploaded.get("auth_mode") or "",
                "folder_name": uploaded.get("folder_name") or "",
            }

        sql = clean_sql(payload.get("cau_lenh_sql") or "")
        binds = payload.get("tham_so") if isinstance(payload.get("tham_so"), dict) else {}
        if not sql:
            raise HTTPException(status_code=400, detail="Thieu cau_lenh_sql.")
        binds = normalize_binds_for_sql(sql, binds)

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
