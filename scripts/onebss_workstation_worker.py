from __future__ import annotations

import argparse
import base64
import fnmatch
import ftplib
import mimetypes
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application.onebss_report_service import OneBssProgressCancelled, run_onebss_report_request
from app.settings import get_settings


class OneBssTaskCancelled(OneBssProgressCancelled):
    pass


class FtpTaskCancelled(Exception):
    pass


TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
WORKER_VERSION = "2026.07.30-synced-oracle-worker"
LOCAL_INTERNAL_API_URL = "http://127.0.0.1:8000/api/du-lieu-web"
LOCAL_DRIVE_UPLOAD_API_URL = "http://127.0.0.1:8000/api/du-lieu-web"
PUBLIC_DRIVE_UPLOAD_API_URL = "https://api.vnptcto.com/api/du-lieu-web"


def response_is_cancelled(data: dict[str, Any]) -> bool:
    return bool(data.get("cancelled")) or str(data.get("status") or "").lower() == "cancelled"


def describe_request_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code if error.response is not None else "?"
        return f"HTTP {status_code}"
    return str(error)[:300] or error.__class__.__name__


def is_transient_request_error(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return bool(error.response is not None and error.response.status_code in TRANSIENT_HTTP_STATUS_CODES)
    return isinstance(error, httpx.RequestError)


def transient_retry_delay_seconds(attempt: int) -> float:
    return min(60.0, max(5.0, float(attempt) * 5.0))


def request_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    retry_forever = bool(kwargs.pop("_retry_forever", True))
    attempt = 0
    while True:
        try:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"ok": True, "data": data}
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            if not is_transient_request_error(error):
                raise
            attempt += 1
            if not retry_forever and attempt >= 3:
                return {"ok": False, "task": None, "transient_error": describe_request_error(error)}
            delay_seconds = transient_retry_delay_seconds(attempt)
            print(
                f"Ket noi web loi tam thoi ({describe_request_error(error)}). "
                f"May tram se thu lai sau {int(delay_seconds)} giay.",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)


def send_heartbeat(client: httpx.Client, worker_id: str, status: str = "idle", message: str = "", details: dict[str, Any] | None = None) -> None:
    payload = {
        "worker_id": worker_id,
        "status": status,
        "roles": ["onebss_worker", "sql_report_worker", "ftp_report_worker", "excel_export", "drive_upload"],
        "version": WORKER_VERSION,
        "local_time": datetime.now().isoformat(timespec="seconds"),
        "message": message,
        "details": {
            "pid": os.getpid(),
            "python": sys.version.split()[0],
            **(details or {}),
        },
    }
    try:
        response = client.post("/api/workstation/heartbeat", json=payload)
        if response.status_code == 404:
            return
        response.raise_for_status()
    except Exception as error:
        print(f"Khong gui duoc heartbeat may tram: {describe_request_error(error)}", file=sys.stderr)


def wait_for_otp(client: httpx.Client, run_id: str, poll_seconds: float, progress_callback=None) -> str:
    if progress_callback:
        progress_callback("Dang doi OTP tu tin nhan/Mobile Gateway.")
    last_notice = time.monotonic()
    while True:
        data = request_json(client, "GET", f"/api/onebss-worker/tasks/{run_id}/otp")
        if response_is_cancelled(data):
            raise OneBssTaskCancelled(str(data.get("message") or "Task OneBSS da bi huy."))
        if data.get("ok") and data.get("otp"):
            if progress_callback:
                progress_callback("Da nhan duoc OTP tu Mobile Gateway.")
            return str(data["otp"])
        if progress_callback and time.monotonic() - last_notice >= 30:
            progress_callback(str(data.get("message") or "Dang doi OTP tu tin nhan/Mobile Gateway."))
            last_notice = time.monotonic()
        time.sleep(poll_seconds)


def _unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        value = str(url or "").strip()
        if not value:
            continue
        key = value.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def _is_public_tunnel_api_url(url: str) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host == "api.vnptcto.com"


def internal_drive_upload_api_urls() -> list[str]:
    configured = os.getenv("ONEBSS_DRIVE_UPLOAD_API_URL", "").strip()
    internal = os.getenv("INTERNAL_API_URL", "").strip()
    urls: list[str] = []
    if not configured or _is_public_tunnel_api_url(configured):
        urls.append(LOCAL_DRIVE_UPLOAD_API_URL)
    urls.extend([configured, internal, PUBLIC_DRIVE_UPLOAD_API_URL])
    return _unique_urls(urls)


def internal_sql_api_urls() -> list[str]:
    configured = os.getenv("SQL_WORKER_API_URL", "").strip() or os.getenv("INTERNAL_API_URL", "").strip()
    urls: list[str] = []
    if not configured or _is_public_tunnel_api_url(configured):
        urls.append(LOCAL_INTERNAL_API_URL)
    urls.append(configured)
    return _unique_urls(urls)


def upload_result_file_to_internal_drive(file_path: str, drive_folder_id: str) -> dict[str, Any]:
    folder_id = str(drive_folder_id or "").strip()
    if not folder_id:
        return {}
    source = Path(str(file_path or ""))
    if not source.exists() or not source.is_file() or source.stat().st_size <= 0:
        return {}
    token = os.getenv("INTERNAL_API_TOKEN", "").strip()
    api_urls = internal_drive_upload_api_urls()
    if not api_urls or not token:
        return {}
    mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    payload = {
        "action": "upload_file_to_drive",
        "source": "onebss-worker",
        "file_name": source.name,
        "file_base64": base64.b64encode(source.read_bytes()).decode("ascii"),
        "content_type": mime_type,
        "drive_folder_id": folder_id,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    timeout_seconds = float(os.getenv("ONEBSS_DRIVE_UPLOAD_TIMEOUT_SECONDS", "300") or "300")
    last_error: Exception | None = None
    for api_url in api_urls:
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=10.0)) as internal_client:
                response = internal_client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            break
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            last_error = error
            if api_url != api_urls[-1]:
                print(f"Khong upload Drive qua {api_url}: {describe_request_error(error)}. Thu endpoint tiep theo.", file=sys.stderr)
                continue
            raise
    else:
        if last_error:
            raise last_error
        return {}
    data = response.json()
    if not isinstance(data, dict) or not data.get("ok"):
        return {}
    drive_url = str(data.get("drive_url") or data.get("storage_link") or data.get("web_view_link") or data.get("web_content_link") or "").strip()
    if not drive_url:
        return {}
    file_id = str(data.get("file_id") or "").strip()
    return {
        "file_name": str(data.get("file_name") or source.name),
        "storage_link": drive_url,
        "storage_status": f"uploaded_google_drive:{file_id}" if file_id else "uploaded_google_drive",
        "message": str(data.get("message") or "Da upload file OneBSS len Google Drive qua API trung gian."),
    }


def upload_task_file(client: httpx.Client, upload_path: str, file_path: str, cancelled_error=OneBssTaskCancelled) -> dict[str, Any]:
    source = Path(str(file_path or ""))
    if not source.exists() or not source.is_file() or source.stat().st_size <= 0:
        return {}
    mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    attempt = 0
    while True:
        try:
            with source.open("rb") as handle:
                response = client.post(
                    upload_path,
                    files={"file": (source.name, handle, mime_type)},
                )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and response_is_cancelled(data):
                raise cancelled_error(str(data.get("message") or "Task da bi huy."))
            uploaded = data.get("file") if isinstance(data.get("file"), dict) else {}
            return uploaded if isinstance(uploaded, dict) else {}
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            if not is_transient_request_error(error):
                raise
            attempt += 1
            delay_seconds = transient_retry_delay_seconds(attempt)
            print(
                f"Ket noi web loi tam thoi khi gui file ({describe_request_error(error)}). "
                f"May tram se thu lai sau {int(delay_seconds)} giay.",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)


def upload_result_file(client: httpx.Client, run_id: str, file_path: str) -> dict[str, Any]:
    return upload_task_file(client, f"/api/onebss-worker/tasks/{run_id}/file", file_path)


def attach_worker_file_if_needed(client: httpx.Client, run_id: str, result: dict[str, Any], drive_folder_id: str = "", progress_callback=None) -> dict[str, Any]:
    storage_status = str(result.get("storage_status") or "").lower()
    if storage_status.startswith("uploaded_google_drive:"):
        return result
    try:
        if drive_folder_id and progress_callback:
            progress_callback("Dang upload file len Google Drive qua API trung gian.")
        drive_uploaded = upload_result_file_to_internal_drive(str(result.get("file_path") or ""), drive_folder_id)
    except Exception as error:
        print(f"Cannot upload OneBSS result to Drive through internal API: {error}", file=sys.stderr)
        if progress_callback:
            progress_callback("Upload Google Drive qua API trung gian loi, dang gui file ve web.")
        drive_uploaded = {}
    if drive_uploaded:
        if progress_callback:
            progress_callback("Da upload file len Google Drive.")
        merged = {**result}
        for key in ("file_name", "storage_link", "storage_status"):
            if drive_uploaded.get(key):
                merged[key] = drive_uploaded.get(key)
        merged["ok"] = True
        merged["status"] = "success"
        merged["message"] = drive_uploaded.get("message") or "Da upload file OneBSS len Google Drive qua API trung gian."
        return merged
    if progress_callback:
        progress_callback("Dang gui file ket qua ve web de co link tai xuong.")
    uploaded = upload_result_file(client, run_id, str(result.get("file_path") or ""))
    if not uploaded:
        return result
    if progress_callback:
        progress_callback("Da gui file ket qua ve web.")
    merged = {**result}
    for key in ("file_name", "file_path", "storage_link", "storage_status"):
        if uploaded.get(key):
            merged[key] = uploaded.get(key)
    failed_only_at_storage = str(result.get("status") or "").lower() in {
        "google_drive_upload_failed",
        "google_drive_not_configured",
        "storage_failed",
    }
    if failed_only_at_storage:
        merged["ok"] = True
        merged["status"] = "success"
        merged["message"] = uploaded.get("message") or "Da tai bao cao OneBSS va gui file ve web."
    return merged


def process_task(client: httpx.Client, task: dict[str, Any], worker_id: str, poll_seconds: float) -> None:
    run_id = str(task.get("run_id") or "")
    report = task.get("report") if isinstance(task.get("report"), dict) else {}
    parameters = task.get("parameters") if isinstance(task.get("parameters"), dict) else {}
    drive_folder_id = str(task.get("drive_folder_id") or "").strip()
    report_for_worker = {**report, "storage_link": ""}
    settings = get_settings().model_copy(update={"mobile_gateway_enabled": False, "google_drive_folder_id": ""})
    session_id = ""
    otp = ""
    started = time.monotonic()
    last_progress = {"message": "", "at": 0.0}

    def send_progress(message: str, status: str = "running") -> None:
        text = str(message or "").strip()
        if not text:
            return
        now = time.monotonic()
        if text == last_progress["message"] and now - float(last_progress["at"] or 0) < 3:
            return
        last_progress["message"] = text
        last_progress["at"] = now
        data = request_json(
            client,
            "POST",
            f"/api/onebss-worker/tasks/{run_id}/status",
            json={
                "status": status,
                "message": text,
                "worker_id": worker_id,
                "worker_session_id": session_id,
            },
        )
        if response_is_cancelled(data):
            raise OneBssTaskCancelled(str(data.get("message") or "Task OneBSS da bi huy."))

    try:
        send_progress("May tram da nhan task OneBSS. Dang khoi tao phien chay.")
        while True:
            result = run_onebss_report_request(
                settings,
                report_for_worker,
                parameters,
                otp=otp,
                session_id=session_id,
                created_by=worker_id,
                progress_callback=send_progress,
            )
            status = str(result.get("status") or ("success" if result.get("ok") else "failed")).lower()
            if status in {"otp_required", "otp_invalid", "manual_otp_required"} and result.get("session_id"):
                session_id = str(result.get("session_id") or "")
                status_response = request_json(
                    client,
                    "POST",
                    f"/api/onebss-worker/tasks/{run_id}/status",
                    json={
                        "status": status,
                        "message": result.get("message") or "May tram dang doi OTP OneBSS.",
                        "worker_id": worker_id,
                        "worker_session_id": session_id,
                    },
                )
                if response_is_cancelled(status_response):
                    return
                otp = wait_for_otp(client, run_id, poll_seconds, lambda message: send_progress(message, status))
                continue

            duration_ms = int((time.monotonic() - started) * 1000)
            send_progress("Da hoan thanh buoc lay du lieu OneBSS. Dang xu ly file ket qua.")
            result = attach_worker_file_if_needed(client, run_id, result, drive_folder_id, send_progress)
            status = str(result.get("status") or ("success" if result.get("ok") else "failed")).lower()
            finish_response = request_json(
                client,
                "POST",
                f"/api/onebss-worker/tasks/{run_id}/result",
                json={
                    "ok": bool(result.get("ok")),
                    "status": status,
                    "message": result.get("message") or "",
                    "file_name": result.get("file_name") or "",
                    "file_path": result.get("file_path") or "",
                    "storage_link": result.get("storage_link") or "",
                    "storage_status": result.get("storage_status") or "",
                    "duration_ms": int(result.get("duration_ms") or duration_ms),
                    "details": result,
                },
            )
            if response_is_cancelled(finish_response):
                return
            return
    except OneBssTaskCancelled as error:
        print(str(error), file=sys.stderr)
        return
    except Exception as error:
        duration_ms = int((time.monotonic() - started) * 1000)
        error_message = str(error)[:500] or error.__class__.__name__
        print(f"Task OneBSS loi: {error_message}", file=sys.stderr)
        try:
            request_json(
                client,
                "POST",
                f"/api/onebss-worker/tasks/{run_id}/result",
                json={
                    "ok": False,
                    "status": "failed",
                    "message": f"May tram gap loi khi lay OneBSS: {error_message}",
                    "duration_ms": duration_ms,
                    "details": {"error_type": error.__class__.__name__},
                },
            )
        except Exception as update_error:
            print(
                f"Khong cap nhat duoc ket qua OneBSS: {describe_request_error(update_error)}",
                file=sys.stderr,
            )
        return


def run_sql_worker_query(task: dict[str, Any]) -> dict[str, Any]:
    query = task.get("query") if isinstance(task.get("query"), dict) else {}
    if not query:
        raise RuntimeError("Task SQL khong co cau lenh truy van.")
    token = os.getenv("INTERNAL_API_TOKEN", "").strip()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    timeout_seconds = float(os.getenv("SQL_WORKER_TIMEOUT_SECONDS", "1800") or "1800")
    api_urls = internal_sql_api_urls()
    if not api_urls:
        raise RuntimeError("Chua cau hinh URL API du lieu local cho SQL worker.")
    last_error: Exception | None = None
    for api_url in api_urls:
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=10.0)) as internal_client:
                response = internal_client.post(api_url, json=query, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"ok": True, "data": data}
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            last_error = error
            if api_url != api_urls[-1]:
                print(f"Khong chay SQL qua {api_url}: {describe_request_error(error)}. Thu endpoint tiep theo.", file=sys.stderr)
                continue
            raise
    if last_error:
        raise last_error
    return {"ok": False, "message": "API du lieu local khong tra ket qua."}


def process_sql_task(client: httpx.Client, task: dict[str, Any], worker_id: str) -> None:
    run_id = str(task.get("run_id") or task.get("job_id") or "")
    started = time.monotonic()

    def send_progress(message: str, status: str = "running_worker", details: dict[str, Any] | None = None) -> None:
        request_json(
            client,
            "POST",
            f"/api/sql-worker/tasks/{run_id}/status",
            json={
                "status": status,
                "message": message,
                "worker_id": worker_id,
                "details": details or {},
            },
        )

    def start_export_heartbeat(report_code: str) -> threading.Event:
        stop_event = threading.Event()

        def heartbeat_loop() -> None:
            while not stop_event.wait(25):
                elapsed_seconds = int(time.monotonic() - started)
                try:
                    send_progress(
                        f"May tram van dang xuat Excel/upload Drive, da chay {elapsed_seconds} giay.",
                        details={
                            "step": "oracle_export_drive",
                            "report": report_code,
                            "elapsed_seconds": elapsed_seconds,
                            "worker_version": WORKER_VERSION,
                        },
                    )
                except Exception as error:
                    print(f"Khong cap nhat duoc tien trinh SQL: {describe_request_error(error)}", file=sys.stderr)

        threading.Thread(
            target=heartbeat_loop,
            name=f"vnptcto-sql-export-{run_id or 'task'}",
            daemon=True,
        ).start()
        return stop_event

    try:
        query = task.get("query") if isinstance(task.get("query"), dict) else {}
        action = str(query.get("action") or "").strip()
        report_code = str(task.get("report_code") or query.get("ma_bao_cao") or "")
        export_heartbeat: threading.Event | None = None
        if action == "export_sql_report_to_drive":
            send_progress(
                "May tram da nhan lenh lay du lieu SQL. Dang chuan bi ket noi Oracle noi bo.",
                details={"step": "received", "report": report_code, "api_urls": internal_sql_api_urls()},
            )
            send_progress(
                "Dang ket noi Oracle noi bo, xuat Excel va upload Google Drive.",
                details={"step": "oracle_export_drive", "report": report_code, "api_urls": internal_sql_api_urls()},
            )
            export_heartbeat = start_export_heartbeat(report_code)
        else:
            send_progress(
                "May tram da nhan task SQL. Dang goi API du lieu local.",
                details={"step": "received", "report": report_code, "api_urls": internal_sql_api_urls()},
            )
        try:
            result = run_sql_worker_query(task)
        finally:
            if export_heartbeat is not None:
                export_heartbeat.set()

        def result_int(*values: Any) -> int:
            for value in values:
                if isinstance(value, list):
                    return len(value)
                try:
                    if value not in (None, ""):
                        return int(value)
                except (TypeError, ValueError):
                    continue
            return 0

        if action == "export_sql_report_to_drive":
            columns = result.get("columns") if isinstance(result.get("columns"), list) else []
            pagination = result.get("pagination") if isinstance(result.get("pagination"), dict) else {}
            total = result_int(result.get("total"), result.get("rows"), pagination.get("total"))
            details = result.get("details") if isinstance(result.get("details"), dict) else {}
            drive_url = str(
                result.get("drive_url")
                or result.get("storage_link")
                or result.get("web_view_link")
                or result.get("web_content_link")
                or ""
            ).strip()
            send_progress(
                "Da nhan ket qua tu API local. Dang cap nhat file va link Drive len web.",
                details={"step": "returning_drive_link", "report": report_code, "drive_url": drive_url},
            )
            details = {
                **details,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "file_id": str(result.get("file_id") or ""),
                "file_name": str(result.get("file_name") or query.get("file_name") or ""),
                "drive_url": drive_url,
                "storage_link": drive_url,
                "rows": total,
                "total": result_int(result.get("total"), total),
            }
            finish_response = request_json(
                client,
                "POST",
                f"/api/sql-worker/tasks/{run_id}/result",
                json={
                    "ok": bool(result.get("ok", True)),
                    "status": "success" if result.get("ok", True) else "failed",
                    "message": result.get("message") or "May tram da xuat Excel va upload Google Drive.",
                    "columns": columns,
                    "rows": [],
                    "pagination": {"page": 1, "page_size": result_int(pagination.get("page_size"), total), "total": total},
                    "report": task.get("report") if isinstance(task.get("report"), dict) else {},
                    "details": details,
                    "drive_url": drive_url,
                    "storage_link": drive_url,
                    "file_name": str(result.get("file_name") or query.get("file_name") or ""),
                    "file_id": str(result.get("file_id") or ""),
                    "total": result_int(result.get("total"), total),
                },
            )
            if response_is_cancelled(finish_response):
                return
            return

        rows = result.get("rows") or result.get("data") or []
        if not isinstance(rows, list):
            rows = []
        columns = result.get("columns") if isinstance(result.get("columns"), list) else []
        if not columns and rows and isinstance(rows[0], dict):
            columns = list(rows[0].keys())
        pagination = {
            "page": int(result.get("page") or ((task.get("query") or {}).get("pagination") or {}).get("page") or 1),
            "page_size": int(result.get("page_size") or ((task.get("query") or {}).get("pagination") or {}).get("page_size") or len(rows) or 20),
            "total": int(result.get("total") or len(rows)),
        }
        details = result.get("details") if isinstance(result.get("details"), dict) else {}
        details = {**details, "duration_ms": int((time.monotonic() - started) * 1000)}
        finish_response = request_json(
            client,
            "POST",
            f"/api/sql-worker/tasks/{run_id}/result",
            json={
                "ok": bool(result.get("ok", True)),
                "status": "success" if result.get("ok", True) else "failed",
                "message": result.get("message") or "May tram da tai du lieu SQL qua API local.",
                "columns": columns,
                "rows": rows,
                "pagination": pagination,
                "report": task.get("report") if isinstance(task.get("report"), dict) else {},
                "details": details,
            },
        )
        if response_is_cancelled(finish_response):
            return
    except Exception as error:
        message = str(error)[:500] or error.__class__.__name__
        print(f"Task SQL loi: {message}", file=sys.stderr)
        try:
            request_json(
                client,
                "POST",
                f"/api/sql-worker/tasks/{run_id}/result",
                json={
                    "ok": False,
                    "status": "failed",
                    "message": f"May tram khong chay duoc SQL qua API local: {message}",
                    "details": {"error_type": error.__class__.__name__},
                },
            )
        except Exception as update_error:
            print(f"Khong cap nhat duoc ket qua SQL: {describe_request_error(update_error)}", file=sys.stderr)


def safe_local_filename(value: str, fallback: str = "ftp_result") -> str:
    text = Path(str(value or fallback)).name.strip() or fallback
    text = "".join("_" if character in '<>:"/\\|?*' or ord(character) < 32 else character for character in text)
    text = text.strip(" .")
    return text or fallback


def render_ftp_file_template(template: str, now: datetime | None = None) -> str:
    current = now or datetime.now()
    yesterday = current - timedelta(days=1)
    values = {
        "yyyy": f"{current:%Y}",
        "YYYY": f"{current:%Y}",
        "yy": f"{current:%y}",
        "YY": f"{current:%y}",
        "mm": f"{current:%m}",
        "MM": f"{current:%m}",
        "m": str(current.month),
        "dd": f"{current:%d}",
        "DD": f"{current:%d}",
        "d": str(current.day),
        "yyyymmdd": f"{current:%Y%m%d}",
        "YYYYMMDD": f"{current:%Y%m%d}",
        "ddmmyyyy": f"{current:%d%m%Y}",
        "DDMMYYYY": f"{current:%d%m%Y}",
        "today": f"{current:%Y%m%d}",
        "today_ddmmyyyy": f"{current:%d%m%Y}",
        "yesterday": f"{yesterday:%Y%m%d}",
        "yesterday_ddmmyyyy": f"{yesterday:%d%m%Y}",
    }
    output = str(template or "").strip()
    for key, value in values.items():
        output = output.replace(f"{{{{{key}}}}}", value).replace(f"{{{key}}}", value)
    return output


def ftp_modified_sort_key(ftp: ftplib.FTP, name: str) -> tuple[str, str]:
    try:
        response = ftp.sendcmd(f"MDTM {name}")
        stamp = response.split(maxsplit=1)[1].strip() if " " in response else response.strip()
        return (stamp, name)
    except Exception:
        return ("", name)


def parse_ftp_task(task: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    connection = task.get("connection") if isinstance(task.get("connection"), dict) else {}
    config = connection.get("config") if isinstance(connection.get("config"), dict) else {}
    ftp_config = dict(config)
    folder_path = str(task.get("folder_path") or "").strip()
    file_template = str(task.get("file_name_template") or "").strip()
    parsed = urlparse(folder_path)
    if parsed.scheme.lower() == "ftp":
        if parsed.hostname:
            ftp_config["host"] = parsed.hostname
        if parsed.port:
            ftp_config["port"] = parsed.port
        if parsed.username and not str(ftp_config.get("username") or "").strip():
            ftp_config["username"] = unquote(parsed.username)
        if parsed.password and not str(ftp_config.get("password") or "").strip():
            ftp_config["password"] = unquote(parsed.password)
        path = unquote(parsed.path or "/")
        if not file_template and path and not path.endswith("/"):
            file_template = Path(path).name
            folder_path = str(Path(path).parent).replace("\\", "/")
        else:
            folder_path = path or "/"
    return ftp_config, folder_path or "/", file_template


def download_ftp_report_file(task: dict[str, Any], progress_callback=None) -> dict[str, Any]:
    config, folder_path, file_template = parse_ftp_task(task)
    host = str(config.get("host") or "").strip()
    username = str(config.get("username") or "").strip()
    password = str(config.get("password") or "")
    port = int(config.get("port") or 21)
    timeout = float(config.get("timeout_seconds") or 60)
    passive = config.get("passive", True) is not False
    if not host or not username or not password:
        raise RuntimeError("FTP thieu host, username hoac password.")
    resolved_name = render_ftp_file_template(file_template)
    if not resolved_name:
        raise RuntimeError("Ten file FTP sau khi render dang rong.")
    if progress_callback:
        progress_callback(f"Dang ket noi FTP {host}:{port}.", "running", resolved_name)
    started = time.monotonic()
    ftp = ftplib.FTP()
    try:
        ftp.connect(host=host, port=port, timeout=timeout)
        ftp.login(user=username, passwd=password)
        ftp.set_pasv(passive)
        if folder_path and folder_path not in {".", "/"}:
            ftp.cwd(folder_path)
        if progress_callback:
            progress_callback(f"Dang tim file {resolved_name}.", "running", resolved_name)
        wildcard = any(character in resolved_name for character in "*?[")
        names = ftp.nlst()
        if wildcard:
            matches = [name for name in names if fnmatch.fnmatch(Path(name).name, resolved_name)]
        else:
            matches = [name for name in names if Path(name).name.lower() == resolved_name.lower()]
            if not matches:
                matches = [resolved_name]
        if not matches:
            raise FileNotFoundError(f"Khong tim thay file FTP: {resolved_name}")
        remote_name = sorted(matches, key=lambda item: ftp_modified_sort_key(ftp, item), reverse=True)[0]
        local_dir = Path(str(get_settings().data_mining_download_dir or "data/data_mining_downloads")) / "ftp"
        local_dir.mkdir(parents=True, exist_ok=True)
        local_name = safe_local_filename(Path(remote_name).name or resolved_name, "ftp_result")
        local_path = (local_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{local_name}").resolve()
        if progress_callback:
            progress_callback(f"Dang tai file {Path(remote_name).name}.", "running", Path(remote_name).name)
        with local_path.open("wb") as handle:
            ftp.retrbinary(f"RETR {remote_name}", handle.write)
        if local_path.stat().st_size <= 0:
            local_path.unlink(missing_ok=True)
            raise RuntimeError("File FTP tai ve rong.")
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": True,
            "status": "success",
            "message": "Da tai file FTP tren may tram.",
            "resolved_file_name": Path(remote_name).name,
            "file_name": local_path.name,
            "file_path": str(local_path),
            "duration_ms": duration_ms,
        }
    finally:
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass


def upload_ftp_result_file(client: httpx.Client, run_id: str, file_path: str) -> dict[str, Any]:
    return upload_task_file(client, f"/api/ftp-worker/tasks/{run_id}/file", file_path, FtpTaskCancelled)


def process_ftp_task(client: httpx.Client, task: dict[str, Any], worker_id: str) -> None:
    run_id = str(task.get("run_id") or "")
    started = time.monotonic()
    last_progress = {"message": "", "at": 0.0}

    def send_progress(message: str, status: str = "running", resolved_file_name: str = "") -> None:
        text = str(message or "").strip()
        if not text:
            return
        now = time.monotonic()
        if text == last_progress["message"] and now - float(last_progress["at"] or 0) < 3:
            return
        last_progress["message"] = text
        last_progress["at"] = now
        data = request_json(
            client,
            "POST",
            f"/api/ftp-worker/tasks/{run_id}/status",
            json={
                "status": status,
                "message": text,
                "worker_id": worker_id,
                "resolved_file_name": resolved_file_name,
            },
        )
        if response_is_cancelled(data):
            raise FtpTaskCancelled(str(data.get("message") or "Task FTP da bi huy."))

    try:
        send_progress("May tram da nhan task FTP. Dang khoi tao ket noi.")
        result = download_ftp_report_file(task, send_progress)
        send_progress("Da tai file FTP. Dang gui file ve web.", "running", str(result.get("resolved_file_name") or ""))
        uploaded = upload_ftp_result_file(client, run_id, str(result.get("file_path") or ""))
        if uploaded:
            for key in ("file_name", "file_path", "storage_link", "storage_status"):
                if uploaded.get(key):
                    result[key] = uploaded.get(key)
        duration_ms = int(result.get("duration_ms") or int((time.monotonic() - started) * 1000))
        finish_response = request_json(
            client,
            "POST",
            f"/api/ftp-worker/tasks/{run_id}/result",
            json={
                "ok": bool(result.get("ok")),
                "status": result.get("status") or ("success" if result.get("ok") else "failed"),
                "message": result.get("message") or "",
                "resolved_file_name": result.get("resolved_file_name") or "",
                "file_name": result.get("file_name") or "",
                "file_path": result.get("file_path") or "",
                "storage_link": result.get("storage_link") or "",
                "storage_status": result.get("storage_status") or "",
                "duration_ms": duration_ms,
                "details": result,
            },
        )
        if response_is_cancelled(finish_response):
            return
    except FtpTaskCancelled as error:
        print(str(error), file=sys.stderr)
        return
    except Exception as error:
        message = str(error)[:500] or error.__class__.__name__
        print(f"Task FTP loi: {message}", file=sys.stderr)
        try:
            request_json(
                client,
                "POST",
                f"/api/ftp-worker/tasks/{run_id}/result",
                json={
                    "ok": False,
                    "status": "failed",
                    "message": message,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "details": {"error_type": error.__class__.__name__},
                },
            )
        except Exception as update_error:
            print(f"Khong cap nhat duoc ket qua FTP: {describe_request_error(update_error)}", file=sys.stderr)


def poll_worker_once(client: httpx.Client, worker_id: str, poll_seconds: float) -> bool:
    claim = request_json(client, "POST", "/api/onebss-worker/tasks/claim", json={"worker_id": worker_id}, timeout=10.0, _retry_forever=False)
    if claim.get("transient_error"):
        return False
    task = claim.get("task") if isinstance(claim.get("task"), dict) else None
    if task:
        send_heartbeat(
            client,
            worker_id,
            "busy",
            f"Dang xu ly task {task.get('run_id') or ''}.",
            {"run_id": task.get("run_id") or "", "report": (task.get("report") or {}).get("ma_bao_cao") if isinstance(task.get("report"), dict) else ""},
        )
        process_task(client, task, worker_id, poll_seconds)
        send_heartbeat(client, worker_id, "idle", "May tram OneBSS da quay lai trang thai cho task.")
        return True

    sql_claim = request_json(client, "POST", "/api/sql-worker/tasks/claim", json={"worker_id": worker_id}, timeout=10.0, _retry_forever=False)
    if sql_claim.get("transient_error"):
        return False
    sql_task = sql_claim.get("task") if isinstance(sql_claim.get("task"), dict) else None
    if sql_task:
        send_heartbeat(
            client,
            worker_id,
            "busy",
            f"Dang xu ly task SQL {sql_task.get('run_id') or ''}.",
            {"run_id": sql_task.get("run_id") or "", "report": sql_task.get("report_code") or "", "task_type": "sql"},
        )
        process_sql_task(client, sql_task, worker_id)
        send_heartbeat(client, worker_id, "idle", "May tram SQL da quay lai trang thai cho task.")
        return True

    ftp_claim = request_json(client, "POST", "/api/ftp-worker/tasks/claim", json={"worker_id": worker_id}, timeout=10.0, _retry_forever=False)
    ftp_task = ftp_claim.get("task") if isinstance(ftp_claim.get("task"), dict) else None
    if ftp_task:
        send_heartbeat(
            client,
            worker_id,
            "busy",
            f"Dang xu ly task FTP {ftp_task.get('run_id') or ''}.",
            {"run_id": ftp_task.get("run_id") or "", "report": ftp_task.get("ma_bao_cao") or "", "task_type": "ftp"},
        )
        process_ftp_task(client, ftp_task, worker_id)
        send_heartbeat(client, worker_id, "idle", "May tram FTP da quay lai trang thai cho task.")
        return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll vnptcto.com for OneBSS/FTP export tasks and run them on this workstation.")
    parser.add_argument("--base-url", default=os.getenv("VNPTCTO_BASE_URL", "https://vnptcto.com"))
    parser.add_argument("--token", default=os.getenv("INTERNAL_API_TOKEN", ""))
    parser.add_argument("--worker-id", default=os.getenv("ONEBSS_WORKER_ID", "onebss-workstation"))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("ONEBSS_WORKER_POLL_SECONDS", "5")))
    parser.add_argument("--heartbeat-seconds", type=float, default=float(os.getenv("ONEBSS_WORKER_HEARTBEAT_SECONDS", "60")))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.token:
        raise SystemExit("Missing INTERNAL_API_TOKEN or --token.")

    headers = {"Authorization": f"Bearer {args.token}"}
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=httpx.Timeout(60.0, connect=20.0)) as client:
        send_heartbeat(client, args.worker_id, "starting", "May tram OneBSS dang khoi dong.")
        last_heartbeat = time.monotonic()
        while True:
            now = time.monotonic()
            if now - last_heartbeat >= max(15.0, args.heartbeat_seconds):
                send_heartbeat(client, args.worker_id, "idle", "May tram OneBSS dang cho task.")
                last_heartbeat = now
            processed = poll_worker_once(client, args.worker_id, args.poll_seconds)
            if processed:
                last_heartbeat = time.monotonic()
            if args.once:
                return 0
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
