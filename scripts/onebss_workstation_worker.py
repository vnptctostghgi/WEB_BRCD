from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application.onebss_report_service import run_onebss_report_request
from app.settings import get_settings


def request_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {"ok": True, "data": data}


def wait_for_otp(client: httpx.Client, run_id: str, poll_seconds: float) -> str:
    while True:
        data = request_json(client, "GET", f"/api/onebss-worker/tasks/{run_id}/otp")
        if data.get("ok") and data.get("otp"):
            return str(data["otp"])
        time.sleep(poll_seconds)


def process_task(client: httpx.Client, task: dict[str, Any], worker_id: str, poll_seconds: float) -> None:
    run_id = str(task.get("run_id") or "")
    report = task.get("report") if isinstance(task.get("report"), dict) else {}
    parameters = task.get("parameters") if isinstance(task.get("parameters"), dict) else {}
    settings = get_settings().model_copy(update={"mobile_gateway_enabled": False})
    session_id = ""
    otp = ""
    started = time.monotonic()

    while True:
        result = run_onebss_report_request(
            settings,
            report,
            parameters,
            otp=otp,
            session_id=session_id,
            created_by=worker_id,
        )
        status = str(result.get("status") or ("success" if result.get("ok") else "failed")).lower()
        if status in {"otp_required", "otp_invalid", "manual_otp_required"} and result.get("session_id"):
            session_id = str(result.get("session_id") or "")
            request_json(
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
            otp = wait_for_otp(client, run_id, poll_seconds)
            continue

        duration_ms = int((time.monotonic() - started) * 1000)
        request_json(
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

    headers = {"Authorization": f"Bearer {args.token}", "Content-Type": "application/json"}
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
