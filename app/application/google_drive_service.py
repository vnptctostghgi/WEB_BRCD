from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet, InvalidToken

from app.settings import Settings


DRIVE_FOLDER_HOSTS = {"drive.google.com", "docs.google.com"}
GOOGLE_DRIVE_CONNECTION_CODE = "drive_storage"
GOOGLE_DRIVE_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
GOOGLE_DRIVE_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/drive"]
GOOGLE_DRIVE_OAUTH_PROVIDER = "google_drive_oauth"


class GoogleDriveConfigurationError(RuntimeError):
    pass


def google_drive_oauth_client_configured(settings: Settings) -> bool:
    return bool(
        str(getattr(settings, "google_drive_oauth_client_id", "") or "").strip()
        and settings.google_drive_oauth_client_secret.get_secret_value().strip()
    )


def extract_google_drive_folder_id(value: Any) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    parsed = urlparse(raw_value)
    if parsed.scheme in {"http", "https"}:
        host = parsed.netloc.lower()
        if host not in DRIVE_FOLDER_HOSTS:
            return ""
        parts = [part for part in parsed.path.split("/") if part]
        if "folders" in parts:
            index = parts.index("folders")
            if len(parts) > index + 1:
                return parts[index + 1].strip()
        query_id = parse_qs(parsed.query).get("id", [""])[0].strip()
        return query_id
    if "/" not in raw_value and len(raw_value) >= 10:
        return raw_value
    return ""


def google_drive_folder_id(settings: Settings, storage_link: str = "") -> str:
    configured_folder = str(getattr(settings, "google_drive_folder_id", "") or "").strip()
    if not configured_folder:
        oauth_config = load_google_drive_oauth_config()
        configured_folder = str(oauth_config.get("folder") or oauth_config.get("folder_id") or "").strip()
    return extract_google_drive_folder_id(storage_link) or configured_folder


def secret_cipher(settings: Settings) -> Fernet:
    secret = settings.session_secret.get_secret_value().encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_secret_value(settings: Settings, value: str) -> str:
    if not value:
        return ""
    return "enc:" + secret_cipher(settings).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret_value(settings: Settings, value: str) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    if not raw_value.startswith("enc:"):
        return raw_value
    try:
        return secret_cipher(settings).decrypt(raw_value[4:].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as error:
        raise GoogleDriveConfigurationError("Khong giai ma duoc token Google Drive. Hay ket noi Drive lai.") from error


def load_google_drive_oauth_config(repository: Any | None = None) -> dict[str, Any]:
    try:
        repo = repository
        if repo is None:
            from app.data_access.repository_factory import build_repository

            repo = build_repository()
        connection = repo.get_system_connection_by_code(GOOGLE_DRIVE_CONNECTION_CODE)
    except Exception:
        return {}
    if not connection:
        return {}
    config = connection.get("config") if isinstance(connection.get("config"), dict) else {}
    return config if isinstance(config, dict) else {}


def oauth_refresh_token_from_config(settings: Settings, config: dict[str, Any]) -> str:
    encrypted = str(config.get("oauth_refresh_token_enc") or "").strip()
    plain = str(config.get("oauth_refresh_token") or "").strip()
    return decrypt_secret_value(settings, encrypted or plain)


def google_drive_oauth_credentials(settings: Settings, repository: Any | None = None) -> tuple[Any, dict[str, Any]] | None:
    config = load_google_drive_oauth_config(repository)
    refresh_token = oauth_refresh_token_from_config(settings, config)
    if not refresh_token:
        return None
    client_id = str(getattr(settings, "google_drive_oauth_client_id", "") or "").strip()
    client_secret = settings.google_drive_oauth_client_secret.get_secret_value().strip()
    if not client_id or not client_secret:
        raise GoogleDriveConfigurationError(
            "Drive da ket noi OAuth nhung thieu GOOGLE_DRIVE_OAUTH_CLIENT_ID/GOOGLE_DRIVE_OAUTH_CLIENT_SECRET."
        )
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as error:
        raise GoogleDriveConfigurationError("May chu chua cai thu vien Google OAuth.") from error
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=str(config.get("oauth_token_uri") or GOOGLE_DRIVE_OAUTH_TOKEN_URI),
        client_id=client_id,
        client_secret=client_secret,
        scopes=GOOGLE_DRIVE_UPLOAD_SCOPES,
    )
    return credentials, config


def save_google_drive_oauth_tokens(
    settings: Settings,
    repository: Any,
    token_data: dict[str, Any],
    *,
    email: str = "",
) -> dict[str, Any]:
    existing = repository.get_system_connection_by_code(GOOGLE_DRIVE_CONNECTION_CODE) or {}
    existing_config = existing.get("config") if isinstance(existing.get("config"), dict) else {}
    refresh_token = str(token_data.get("refresh_token") or "").strip()
    if not refresh_token:
        refresh_token = oauth_refresh_token_from_config(settings, existing_config)
    if not refresh_token:
        raise GoogleDriveConfigurationError("Google chua tra refresh_token. Hay thu ket noi lai voi prompt consent.")
    now_text = token_data.get("connected_at") or ""
    config = {
        **existing_config,
        "provider": GOOGLE_DRIVE_OAUTH_PROVIDER,
        "oauth_email": email or existing_config.get("oauth_email") or "",
        "oauth_scope": token_data.get("scope") or " ".join(GOOGLE_DRIVE_UPLOAD_SCOPES),
        "oauth_token_uri": GOOGLE_DRIVE_OAUTH_TOKEN_URI,
        "oauth_connected_at": now_text,
        "oauth_refresh_token_enc": encrypt_secret_value(settings, refresh_token),
    }
    config.pop("oauth_refresh_token", None)
    repository.upsert_system_connection(
        GOOGLE_DRIVE_CONNECTION_CODE,
        str(existing.get("name") or "Google Drive"),
        "drive",
        str(existing.get("description") or "Google Drive OAuth upload cho OneBSS."),
        config,
        True,
    )
    return config


def clear_google_drive_oauth_tokens(repository: Any) -> dict[str, Any]:
    existing = repository.get_system_connection_by_code(GOOGLE_DRIVE_CONNECTION_CODE) or {}
    config = existing.get("config") if isinstance(existing.get("config"), dict) else {}
    cleaned = {
        key: value for key, value in config.items()
        if not str(key).startswith("oauth_")
    }
    if cleaned.get("provider") == GOOGLE_DRIVE_OAUTH_PROVIDER:
        cleaned["provider"] = ""
    repository.upsert_system_connection(
        GOOGLE_DRIVE_CONNECTION_CODE,
        str(existing.get("name") or "Google Drive"),
        "drive",
        str(existing.get("description") or "Ket noi Drive/Cloud storage."),
        cleaned,
        False,
    )
    return cleaned


def google_drive_oauth_status(settings: Settings, repository: Any | None = None) -> dict[str, Any]:
    config = load_google_drive_oauth_config(repository)
    token_error = ""
    try:
        connected = bool(oauth_refresh_token_from_config(settings, config))
    except GoogleDriveConfigurationError as error:
        connected = False
        token_error = str(error)
    folder_id = str(config.get("folder") or config.get("folder_id") or getattr(settings, "google_drive_folder_id", "") or "").strip()
    return {
        "connected": connected,
        "client_configured": google_drive_oauth_client_configured(settings),
        "email": str(config.get("oauth_email") or "").strip(),
        "provider": str(config.get("provider") or "").strip(),
        "connected_at": str(config.get("oauth_connected_at") or "").strip(),
        "folder_id": folder_id,
        "folder_link": f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else "",
        "token_error": token_error,
    }


def load_service_account_info(settings: Settings) -> dict[str, Any]:
    raw_base64 = settings.google_drive_service_account_json_base64.get_secret_value().strip()
    raw_json = settings.google_drive_service_account_json.get_secret_value().strip()
    file_path = str(getattr(settings, "google_drive_service_account_file", "") or "").strip()
    if raw_base64:
        try:
            raw_json = base64.b64decode(raw_base64).decode("utf-8")
        except Exception as error:
            raise GoogleDriveConfigurationError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_BASE64 khong doc duoc.") from error
    elif file_path:
        try:
            raw_json = Path(file_path).read_text(encoding="utf-8")
        except OSError as error:
            raise GoogleDriveConfigurationError("Khong doc duoc file service account Google Drive.") from error
    if not raw_json:
        raise GoogleDriveConfigurationError("Chua cau hinh service account Google Drive.")
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise GoogleDriveConfigurationError("Service account Google Drive khong phai JSON hop le.") from error
    if not info.get("client_email") or not info.get("private_key"):
        raise GoogleDriveConfigurationError("Service account Google Drive thieu client_email/private_key.")
    return info


def upload_file_to_google_drive(settings: Settings, local_path: Path, file_name: str, folder_id: str, mime_type: str = "") -> dict[str, Any]:
    if not folder_id:
        raise GoogleDriveConfigurationError("Chua cau hinh folder_id Google Drive.")
    oauth_credentials = google_drive_oauth_credentials(settings)
    if oauth_credentials:
        credentials, oauth_config = oauth_credentials
        return upload_with_credentials(
            credentials,
            local_path,
            file_name,
            folder_id,
            mime_type=mime_type,
            auth_mode="oauth",
            principal=str(oauth_config.get("oauth_email") or ""),
        )
    info = load_service_account_info(settings)
    try:
        from google.oauth2 import service_account
    except ImportError as error:
        raise GoogleDriveConfigurationError("May chu chua cai thu vien Google Drive API.") from error

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    impersonated_user = str(getattr(settings, "google_drive_impersonated_user", "") or "").strip()
    if impersonated_user:
        credentials = credentials.with_subject(impersonated_user)
    result = upload_with_credentials(
        credentials,
        local_path,
        file_name,
        folder_id,
        mime_type=mime_type,
        auth_mode="service_account",
        principal=impersonated_user or str(info.get("client_email") or ""),
    )
    result["client_email"] = info.get("client_email") or ""
    return result


def upload_with_credentials(
    credentials: Any,
    local_path: Path,
    file_name: str,
    folder_id: str,
    *,
    mime_type: str = "",
    auth_mode: str,
    principal: str = "",
) -> dict[str, Any]:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as error:
        raise GoogleDriveConfigurationError("May chu chua cai thu vien Google Drive API.") from error

    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    media = MediaFileUpload(
        str(local_path),
        mimetype=mime_type or guess_excel_mimetype(local_path),
        resumable=True,
    )
    metadata = {"name": file_name, "parents": [folder_id]}
    uploaded = drive.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink,webContentLink",
        supportsAllDrives=True,
    ).execute()
    return {
        "ok": True,
        "status": "uploaded_google_drive",
        "file_id": uploaded.get("id") or "",
        "file_name": uploaded.get("name") or file_name,
        "web_view_link": uploaded.get("webViewLink") or "",
        "web_content_link": uploaded.get("webContentLink") or "",
        "folder_id": folder_id,
        "auth_mode": auth_mode,
        "principal": principal,
    }


def test_google_drive_connection(settings: Settings, repository: Any | None = None) -> dict[str, Any]:
    status = google_drive_oauth_status(settings, repository)
    if not status["connected"]:
        return {
            "ok": False,
            "message": "Google Drive chua ket noi OAuth. Hay bam Ket noi Google Drive.",
            "details": status,
        }
    try:
        credentials_pair = google_drive_oauth_credentials(settings, repository)
        if not credentials_pair:
            raise GoogleDriveConfigurationError("Chua co refresh token Google Drive.")
        credentials, _ = credentials_pair
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        credentials.refresh(Request())
        drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        about = drive.about().get(fields="user").execute()
        return {
            "ok": True,
            "message": "Google Drive OAuth san sang upload file.",
            "details": {**status, "drive_user": about.get("user") or {}},
        }
    except Exception as error:
        return {
            "ok": False,
            "message": f"Google Drive OAuth chua dung: {str(error)[:300]}",
            "details": status,
        }


def guess_excel_mimetype(local_path: Path) -> str:
    suffix = local_path.suffix.lower()
    if suffix == ".xls":
        return "application/vnd.ms-excel"
    if suffix == ".csv":
        return "text/csv"
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
