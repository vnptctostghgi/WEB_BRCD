from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application.onebss_report_service import OneBssProgressCancelled, run_onebss_report_request
from app.settings import get_settings


class OneBssTaskCancelled(OneBssProgressCancelled):
    pass


def response_is_cancelled(data: dict[str, Any]) -> bool:
    return bool(data.get("cancelled")) or str(data.get("status") or "").lower() == "cancelled"


def request_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {"ok": True, "data": data}


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


def internal_drive_upload_api_url() -> str:
    return (
        os.getenv("ONEBSS_DRIVE_UPLOAD_API_URL", "").strip()
        or os.getenv("INTERNAL_API_URL", "").strip()
        or "https://api.vnptcto.com/api/du-lieu-web"
    )


def upload_result_file_to_internal_drive(file_path: str, drive_folder_id: str) -> dict[str, Any]:
    folder_id = str(drive_folder_id or "").strip()
    if not folder_id:
        return {}
    source = Path(str(file_path or ""))
    if not source.exists() or not source.is_file() or source.stat().st_size <= 0:
        return {}
    api_url = internal_drive_upload_api_url()
    token = os.getenv("INTERNAL_API_TOKEN", "").strip()
    if not api_url or not token:
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
    with httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=20.0)) as internal_client:
        response = internal_client.post(api_url, json=payload, headers=headers)
    response.raise_for_status()
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


def upload_result_file(client: httpx.Client, run_id: str, file_path: str) -> dict[str, Any]:
    source = Path(str(file_path or ""))
    if not source.exists() or not source.is_file() or source.stat().st_size <= 0:
        return {}
    mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    with source.open("rb") as handle:
        response = client.post(
            f"/api/onebss-worker/tasks/{run_id}/file",
            files={"file": (source.name, handle, mime_type)},
        )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and response_is_cancelled(data):
        raise OneBssTaskCancelled(str(data.get("message") or "Task OneBSS da bi huy."))
    uploaded = data.get("file") if isinstance(data.get("file"), dict) else {}
    return uploaded if isinstance(uploaded, dict) else {}


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll vnptcto.com for OneBSS export tasks and run them on this workstation.")
    parser.add_argument("--base-url", default=os.getenv("VNPTCTO_BASE_URL", "https://vnptcto.com"))
    parser.add_argument("--token", default=os.getenv("INTERNAL_API_TOKEN", ""))
    parser.add_argument("--worker-id", default=os.getenv("ONEBSS_WORKER_ID", "onebss-workstation"))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("ONEBSS_WORKER_POLL_SECONDS", "5")))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.token:
        raise SystemExit("Missing INTERNAL_API_TOKEN or --token.")

    headers = {"Authorization": f"Bearer {args.token}"}
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=httpx.Timeout(60.0, connect=20.0)) as client:
        while True:
            claim = request_json(client, "POST", "/api/onebss-worker/tasks/claim", json={"worker_id": args.worker_id})
            task = claim.get("task") if isinstance(claim.get("task"), dict) else None
            if task:
                process_task(client, task, args.worker_id, args.poll_seconds)
            if args.once:
                return 0
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
