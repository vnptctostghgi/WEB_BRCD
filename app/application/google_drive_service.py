from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.settings import Settings


DRIVE_FOLDER_HOSTS = {"drive.google.com", "docs.google.com"}


class GoogleDriveConfigurationError(RuntimeError):
    pass


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
    return extract_google_drive_folder_id(storage_link) or str(getattr(settings, "google_drive_folder_id", "") or "").strip()


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


def upload_file_to_google_drive(settings: Settings, local_path: Path, file_name: str, folder_id: str) -> dict[str, Any]:
    if not folder_id:
        raise GoogleDriveConfigurationError("Chua cau hinh folder_id Google Drive.")
    info = load_service_account_info(settings)
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as error:
        raise GoogleDriveConfigurationError("May chu chua cai thu vien Google Drive API.") from error

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    impersonated_user = str(getattr(settings, "google_drive_impersonated_user", "") or "").strip()
    if impersonated_user:
        credentials = credentials.with_subject(impersonated_user)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    media = MediaFileUpload(
        str(local_path),
        mimetype=guess_excel_mimetype(local_path),
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
        "client_email": info.get("client_email") or "",
    }


def guess_excel_mimetype(local_path: Path) -> str:
    suffix = local_path.suffix.lower()
    if suffix == ".xls":
        return "application/vnd.ms-excel"
    if suffix == ".csv":
        return "text/csv"
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
