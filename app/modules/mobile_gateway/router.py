from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.application.google_drive_service import GoogleDriveConfigurationError, upload_file_to_google_drive
from app.data_access.repository_factory import build_repository
from app.modules.mobile_gateway import security
from app.modules.mobile_gateway.event_bus import mobile_gateway_events
from app.modules.mobile_gateway.exceptions import PairingError
from app.modules.mobile_gateway.notification_service import NotificationService
from app.modules.mobile_gateway.otp_service import OtpService
from app.modules.mobile_gateway.pairing_service import PairingService
from app.modules.mobile_gateway.permissions import has_mobile_permission, require_mobile_permission
from app.modules.mobile_gateway.repository import MobileGatewayRepository
from app.modules.mobile_gateway.schemas import (
    AdminCommandPayload,
    ClipboardPayload,
    CommandResultPayload,
    DevicePolicyPayload,
    DeviceUpdatePayload,
    DiagnosticsPayload,
    HeartbeatPayload,
    NotificationBatchPayload,
    OtpConfigurationPayload,
    OtpFilterPayload,
    OtpRegexTestPayload,
    OtpRequestCreatePayload,
    PairingCodeCreatePayload,
    PairDevicePayload,
    SmsBatchPayload,
)
from app.modules.mobile_gateway.sms_service import SmsService
from app.settings import get_settings


router = APIRouter(prefix="/api/mobile-gateway", tags=["mobile-gateway"])
admin_router = APIRouter(prefix="/api/admin/mobile-gateway", tags=["admin-mobile-gateway"])
MOBILE_MEDIA_DRIVE_FOLDER_ID = "1BHXfVDbIPqvgFSX7K1Fz25OJLlUpOris"
ADMIN_TABLE_PAGE_SIZE = 20
MEDIA_LIMITS = {
    "image/jpeg": ("image", 20 * 1024 * 1024),
    "image/png": ("image", 20 * 1024 * 1024),
    "video/mp4": ("video", 250 * 1024 * 1024),
}
DEVICE_AUTH_CACHE_SECONDS = 30
_DEVICE_AUTH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def admin_table_limit(value: int | str | None = None, default: int = ADMIN_TABLE_PAGE_SIZE) -> int:
    try:
        raw_value = int(value if value is not None else default)
    except (TypeError, ValueError):
        raw_value = default
    return min(max(raw_value, 1), ADMIN_TABLE_PAGE_SIZE)


def mobile_repository() -> MobileGatewayRepository:
    settings = get_settings()
    return MobileGatewayRepository(build_repository(settings), settings)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else ""


def cached_device_record(repository: MobileGatewayRepository, device_id: str) -> dict[str, Any] | None:
    now = time.monotonic()
    cached = _DEVICE_AUTH_CACHE.get(device_id)
    if cached and cached[0] > now:
        return cached[1]
    device = repository.get_device_record(device_id)
    if device and bool(device.get("is_active")):
        _DEVICE_AUTH_CACHE[device_id] = (now + DEVICE_AUTH_CACHE_SECONDS, device)
    else:
        _DEVICE_AUTH_CACHE.pop(device_id, None)
    return device


def epoch_millis(value: Any) -> int:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000)
    except ValueError:
        return 0


async def authenticated_device(request: Request) -> dict[str, Any]:
    settings = get_settings()
    if not bool(getattr(settings, "mobile_gateway_enabled", True)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mobile Gateway is disabled.")
    repository = mobile_repository()
    device_id = request.headers.get("X-Device-Id", "").strip()
    timestamp = request.headers.get("X-Timestamp", "").strip()
    nonce = request.headers.get("X-Nonce", "").strip()
    body_hash = request.headers.get("X-Body-SHA256", "").strip()
    signature = request.headers.get("X-Signature", "").strip()
    if not all([device_id, timestamp, nonce, body_hash, signature]):
        raise security.generic_auth_error()
    device = cached_device_record(repository, device_id)
    if not device or not bool(device.get("is_active")):
        raise security.generic_auth_error()
    parsed_timestamp = security.parse_device_timestamp(timestamp)
    if not parsed_timestamp:
        raise security.generic_auth_error()
    skew = int(getattr(settings, "mobile_gateway_hmac_max_clock_skew_seconds", 300) or 300)
    now = datetime.now(UTC)
    if abs((now - parsed_timestamp).total_seconds()) > skew:
        raise security.generic_auth_error()
    body = await security.read_request_body(request)
    if not security.verify_body_hash(body, body_hash):
        raise security.generic_auth_error()
    secret = repository.device_secret(device)
    canonical = "\n".join([request.method.upper(), request.url.path, timestamp, nonce, body_hash])
    if not secret or not security.verify_signature(secret, canonical, signature):
        raise security.generic_auth_error()
    try:
        repository.save_nonce(device_id, nonce, (now + timedelta(seconds=skew)).isoformat(timespec="seconds"))
    except sqlite3.IntegrityError as error:
        raise security.generic_auth_error() from error
    request.state.mobile_device_id = device_id
    request.state.mobile_repository = repository
    return {"device_id": device_id, "device": repository.decode_device(device), "repository": repository}


@router.post("/devices/pair")
def pair_device(request: Request, payload: PairDevicePayload) -> dict[str, Any]:
    try:
        return PairingService(mobile_repository()).pair_device(payload, client_ip(request))
    except PairingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/messages/sms/batch")
async def sync_sms_batch(payload: SmsBatchPayload, context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    return SmsService(context["repository"]).save_batch(context["device_id"], payload.messages)


@router.post("/messages/notifications/batch")
async def sync_notifications_batch(payload: NotificationBatchPayload, context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    return NotificationService(context["repository"]).save_batch(context["device_id"], payload.notifications)


@router.post("/device/heartbeat")
async def device_heartbeat(request: Request, payload: HeartbeatPayload, context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    context["repository"].save_heartbeat(context["device_id"], payload, client_ip(request))
    return {"ok": True, "message": "Heartbeat accepted"}


@router.get("/device/policy")
async def device_policy(context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    repository = context["repository"]
    repository.ensure_defaults()
    policy = repository.get_policy(context["device_id"])
    filters = repository.list_otp_filters(enabled_only=True)
    return {
        "ok": True,
        "policy": {
            "notification_allowlist": policy.get("notification_allowlist") or [],
            "heartbeat_interval_minutes": policy.get("heartbeat_interval_minutes") or 15,
            "sync_interval_minutes": policy.get("sync_interval_minutes") or 15,
            "batch_size": policy.get("batch_size") or 50,
            "sms_enabled": bool(policy.get("sms_enabled")),
            "notifications_enabled": bool(policy.get("notifications_enabled")),
            "clipboard_enabled": bool(policy.get("clipboard_enabled")),
            "camera_enabled": bool(policy.get("camera_enabled")),
            "diagnostics_enabled": bool(policy.get("diagnostics_enabled")),
            "minimum_app_version": policy.get("minimum_app_version") or "1.3.0",
            "force_update": bool(policy.get("force_update")),
            "local_retention_days": policy.get("local_retention_days") or 14,
            "otp_filters": [
                {
                    "id": item.get("filter_id") or item.get("id"),
                    "sender_pattern": item.get("sender_pattern") or "",
                    "sender_match_type": item.get("sender_match_type") or "contains",
                    "otp_length": item.get("otp_length") or 6,
                    "start_prefix": item.get("start_prefix") or "",
                    "validity_seconds": item.get("validity_seconds") or 60,
                    "enabled": bool(item.get("enabled")),
                }
                for item in filters
            ],
        },
    }


@router.get("/device/commands")
async def device_commands(context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    commands = context["repository"].deliver_pending_commands(context["device_id"])
    device_commands = [
        {
            "command_id": command.get("command_id"),
            "type": command.get("command_type") or command.get("type") or "",
            "payload": command.get("payload") or {},
            "expires_at": epoch_millis(command.get("expires_at")),
        }
        for command in commands
    ]
    return {"ok": True, "commands": device_commands}


@router.post("/device/commands/{command_id}/result")
async def device_command_result(command_id: str, payload: CommandResultPayload, context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    context["repository"].finish_command(command_id, context["device_id"], payload.status, payload.result, payload.sanitized_error)
    return {"ok": True}


@router.post("/device/diagnostics")
async def device_diagnostics(payload: DiagnosticsPayload, context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    context["repository"].save_diagnostics(context["device_id"], payload.model_dump())
    return {"ok": True}


@router.post("/clipboard")
async def clipboard(payload: ClipboardPayload, context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    policy = context["repository"].get_policy(context["device_id"])
    return {"ok": True, "accepted": bool(policy.get("clipboard_enabled")), "message": "Clipboard sync is policy-controlled."}


@router.post("/media/upload")
async def upload_media(
    command_id: str = Form(""),
    media_type: str = Form(""),
    captured_at: str = Form(""),
    file: UploadFile = File(...),
    context: dict[str, Any] = Depends(authenticated_device),
) -> dict[str, Any]:
    repository = context["repository"]
    policy = repository.get_policy(context["device_id"])
    if not bool(policy.get("camera_enabled")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Camera/media is disabled by policy.")
    content_type = str(file.content_type or "").lower()
    if content_type not in MEDIA_LIMITS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dinh dang media khong duoc ho tro.")
    expected_type, max_size = MEDIA_LIMITS[content_type]
    normalized_type = str(media_type or expected_type).strip().lower()
    if normalized_type not in {"image", "video"} or normalized_type != expected_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="media_type khong khop voi file.")
    safe_name = Path(file.filename or f"mobile-{command_id or 'media'}").name
    suffix = Path(safe_name).suffix or (".mp4" if normalized_type == "video" else ".jpg")
    drive_name = f"{context['device_id']}-{command_id or 'manual'}-{int(datetime.now(UTC).timestamp())}{suffix}"
    temp_path = Path(tempfile.gettempdir()) / f"mobile-media-{context['device_id']}-{command_id or 'manual'}-{int(datetime.now(UTC).timestamp() * 1000)}{suffix}"
    size_bytes = 0
    try:
        with temp_path.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_size:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File media vuot gioi han.")
                handle.write(chunk)
        try:
            upload = upload_file_to_google_drive(get_settings(), temp_path, drive_name, MOBILE_MEDIA_DRIVE_FOLDER_ID, mime_type=content_type)
            media = repository.save_media(
                {
                    "device_id": context["device_id"],
                    "command_id": command_id,
                    "media_type": normalized_type,
                    "file_name": drive_name,
                    "mime_type": content_type,
                    "size_bytes": size_bytes,
                    "captured_at": captured_at or None,
                    "uploaded_at": repository.now(),
                    "drive_file_id": upload.get("file_id") or "",
                    "drive_url": upload.get("web_view_link") or upload.get("web_content_link") or "",
                    "status": "uploaded",
                    "error_message": "",
                }
            )
        except GoogleDriveConfigurationError as error:
            media = repository.save_media(
                {
                    "device_id": context["device_id"],
                    "command_id": command_id,
                    "media_type": normalized_type,
                    "file_name": drive_name,
                    "mime_type": content_type,
                    "size_bytes": size_bytes,
                    "captured_at": captured_at or None,
                    "uploaded_at": repository.now(),
                    "status": "upload_failed",
                    "error_message": str(error),
                }
            )
            return {
                "ok": False,
                "media": media,
                "media_id": str(media.get("id") or ""),
                "drive_file_id": media.get("drive_file_id") or "",
                "drive_url": media.get("drive_url") or "",
                "message": "Google Drive chua san sang upload media.",
            }
        return {
            "ok": True,
            "media": media,
            "media_id": str(media.get("id") or ""),
            "drive_file_id": media.get("drive_file_id") or "",
            "drive_url": media.get("drive_url") or "",
        }
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


@admin_router.get("/overview")
def admin_overview(request: Request) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.view")
    repository = mobile_repository()
    settings = get_settings()
    threshold = int(getattr(settings, "mobile_gateway_online_threshold_seconds", 180) or 180)
    overview = repository.overview_counts(threshold)
    overview["settings"] = {
        "pairing_ttl_seconds": int(getattr(settings, "mobile_gateway_pairing_ttl_seconds", 0) or 0),
        "online_threshold_seconds": threshold,
    }
    return {"ok": True, "overview": overview}


@admin_router.get("/events")
async def admin_events(request: Request) -> StreamingResponse:
    require_mobile_permission(request, "mobile_gateway.view")

    async def event_stream():
        queue = mobile_gateway_events.subscribe()
        try:
            yield "event: ready\ndata: {\"ok\": true}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    yield f"event: {event.get('type', 'message')}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            mobile_gateway_events.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@admin_router.get("/devices")
def admin_devices(request: Request) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.devices.view")
    repository = mobile_repository()
    threshold = int(getattr(get_settings(), "mobile_gateway_online_threshold_seconds", 180) or 180)
    cutoff = datetime.now(UTC) - timedelta(seconds=threshold)
    heartbeats = repository.latest_heartbeats()
    devices = []
    for device in repository.list_devices():
        heartbeat = heartbeats.get(str(device.get("device_id"))) or {}
        policy = repository.get_policy(str(device.get("device_id") or ""))
        try:
            seen = datetime.fromisoformat(str(device.get("last_seen_at") or "").replace("Z", "+00:00"))
            online = bool(device.get("is_active")) and seen >= cutoff
        except ValueError:
            online = False
        devices.append({**device, "online": online, "heartbeat": heartbeat, "policy": policy})
    return {"ok": True, "devices": devices}


@admin_router.post("/pairing-codes")
def admin_create_pairing_code(request: Request, payload: PairingCodeCreatePayload = PairingCodeCreatePayload()) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.devices.manage")
    result = PairingService(mobile_repository()).create_pairing_code(actor["username"], payload.model_dump())
    mobile_repository().base.add_audit_log(actor["username"], "mobile_pairing_code_created", "Tao ma ghep noi Mobile Gateway")
    return result


@admin_router.get("/pairing-codes")
def admin_pairing_codes(request: Request) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.devices.manage")
    return {"ok": True, "codes": mobile_repository().list_pairing_codes()}


@admin_router.put("/devices/{device_id}")
def admin_update_device(request: Request, device_id: str, payload: DeviceUpdatePayload) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.devices.manage")
    mobile_repository().update_device(device_id, {"name": payload.name.strip()})
    mobile_repository().base.add_audit_log(actor["username"], "mobile_device_updated", f"Cap nhat thiet bi {device_id}")
    return {"ok": True}


@admin_router.post("/devices/{device_id}/revoke")
def admin_revoke_device(request: Request, device_id: str) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.devices.manage")
    now = mobile_repository().now()
    repo = mobile_repository()
    repo.update_device(device_id, {"is_active": False, "revoked_at": now})
    repo.base.add_audit_log(actor["username"], "mobile_device_revoked", f"Thu hoi thiet bi {device_id}")
    return {"ok": True}


@admin_router.post("/devices/{device_id}/reactivate")
def admin_reactivate_device(request: Request, device_id: str) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.devices.manage")
    repo = mobile_repository()
    repo.update_device(device_id, {"is_active": True, "revoked_at": None})
    repo.base.add_audit_log(actor["username"], "mobile_device_reactivated", f"Kich hoat lai thiet bi {device_id}")
    return {"ok": True}


@admin_router.post("/devices/{device_id}/delete")
def admin_delete_device(request: Request, device_id: str) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.devices.manage")
    repo = mobile_repository()
    device = repo.get_device(device_id)
    if not device:
        return {"ok": True}
    threshold = int(getattr(get_settings(), "mobile_gateway_online_threshold_seconds", 180) or 180)
    cutoff = datetime.now(UTC) - timedelta(seconds=threshold)
    online = False
    try:
        seen = datetime.fromisoformat(str(device.get("last_seen_at") or "").replace("Z", "+00:00"))
        online = bool(device.get("is_active")) and seen >= cutoff
    except ValueError:
        online = False
    if online:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chi xoa thiet bi da ngung ket noi.")
    repo.delete_device(device_id)
    repo.base.add_audit_log(actor["username"], "mobile_device_deleted", f"Xoa thiet bi Mobile Gateway {device_id}")
    return {"ok": True}


@admin_router.get("/devices/{device_id}/policy")
def admin_get_policy(request: Request, device_id: str) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.devices.view")
    return {"ok": True, "policy": mobile_repository().get_policy(device_id)}


@admin_router.put("/devices/{device_id}/policy")
def admin_save_policy(request: Request, device_id: str, payload: DevicePolicyPayload) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.devices.manage")
    policy = mobile_repository().save_policy(device_id, payload, actor["username"])
    mobile_repository().base.add_audit_log(actor["username"], "mobile_policy_saved", f"Luu policy thiet bi {device_id}")
    return {"ok": True, "policy": policy}


@admin_router.get("/sms")
def admin_sms(
    request: Request,
    page: int = 1,
    page_size: int = ADMIN_TABLE_PAGE_SIZE,
    device_id: str = "",
    sender: str = "",
    query: str = "",
    date_from: str = "",
    date_to: str = "",
    sim_slot: str = "",
    otp_only: bool = False,
) -> dict[str, Any]:
    user = require_mobile_permission(request, "mobile_gateway.sms.view")
    data = mobile_repository().list_sms(
        page=page,
        page_size=admin_table_limit(page_size),
        device_id=device_id,
        sender=sender,
        query=query,
        date_from=date_from,
        date_to=date_to,
        sim_slot=sim_slot,
        otp_only=otp_only,
    )
    can_view_content = has_mobile_permission(user, "mobile_gateway.sms.view_content")
    if not can_view_content:
        for item in data["items"]:
            masked = security.mask_otp_text(item.get("body") or item.get("body_masked") or "")
            item["body"] = masked
            item["body_masked"] = masked
    elif can_view_content:
        for item in data["items"]:
            body = item.get("body") or item.get("body_masked") or ""
            item["body"] = body
            item["body_masked"] = body
    return {"ok": True, **data}


@admin_router.get("/notifications")
def admin_notifications(request: Request, page: int = 1, page_size: int = ADMIN_TABLE_PAGE_SIZE, device_id: str = "", package_name: str = "", query: str = "") -> dict[str, Any]:
    user = require_mobile_permission(request, "mobile_gateway.notifications.view")
    data = mobile_repository().list_notifications(page=page, page_size=admin_table_limit(page_size), device_id=device_id, package_name=package_name, query=query)
    items = data["items"]
    if not has_mobile_permission(user, "mobile_gateway.notifications.view_content"):
        for item in items:
            masked = security.mask_otp_text(item.get("text") or item.get("text_masked") or "")
            item["text"] = masked
            item["text_masked"] = masked
    else:
        for item in items:
            text = item.get("text") or item.get("text_masked") or ""
            item["text"] = text
            item["text_masked"] = text
    return {"ok": True, **data}


@admin_router.get("/commands")
def admin_commands(request: Request, device_id: str = "", limit: int = ADMIN_TABLE_PAGE_SIZE) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.commands.view")
    return {"ok": True, "commands": mobile_repository().list_commands(device_id=device_id, limit=admin_table_limit(limit))}


@admin_router.post("/commands")
def admin_create_command(request: Request, payload: AdminCommandPayload) -> dict[str, Any]:
    required_permission = "mobile_gateway.media.manage" if payload.command_type in {"capture_photo", "record_video"} else "mobile_gateway.commands.manage"
    actor = require_mobile_permission(request, required_permission)
    command = mobile_repository().create_command(payload.device_id, payload.command_type, payload.payload, actor["username"], payload.ttl_seconds)
    mobile_repository().base.add_audit_log(actor["username"], "mobile_command_created", f"Gui lenh {payload.command_type} toi {payload.device_id}")
    return {"ok": True, "command": command}


@admin_router.get("/media")
def admin_media(request: Request, page: int = 1, page_size: int = ADMIN_TABLE_PAGE_SIZE, device_id: str = "", media_type: str = "") -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.media.view")
    data = mobile_repository().list_media(page=page, page_size=admin_table_limit(page_size), device_id=device_id, media_type=media_type)
    return {"ok": True, **data}


@admin_router.get("/diagnostics")
def admin_diagnostics(request: Request, limit: int = ADMIN_TABLE_PAGE_SIZE) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.audit.view")
    return {"ok": True, "items": mobile_repository().list_diagnostics(admin_table_limit(limit))}


@admin_router.get("/otp/configurations")
def admin_otp_configurations(request: Request) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.otp.view")
    repository = mobile_repository()
    repository.ensure_defaults()
    return {"ok": True, "configurations": repository.list_otp_configurations()}


@admin_router.get("/otp/filters")
def admin_otp_filters(request: Request) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.otp.view")
    repository = mobile_repository()
    repository.ensure_defaults()
    return {"ok": True, "filters": repository.list_otp_filters()}


@admin_router.post("/otp/filters")
def admin_save_otp_filter(request: Request, payload: OtpFilterPayload) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.otp.manage")
    repository = mobile_repository()
    otp_filter = repository.save_otp_filter(payload)
    latest = OtpService(repository).rematch_latest_for_filter(otp_filter)
    repository.base.add_audit_log(actor["username"], "mobile_otp_filter_saved", f"Luu quy tac OTP {otp_filter.get('filter_id')}")
    return {"ok": True, "filter": otp_filter, "latest": latest}


@admin_router.get("/otp/latest")
def admin_otp_latest(request: Request, limit: int = ADMIN_TABLE_PAGE_SIZE) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.otp.view")
    repository = mobile_repository()
    repository.ensure_defaults()
    safe_limit = admin_table_limit(limit)
    items = repository.list_otp_latest_values(safe_limit)
    seen_filter_ids = {str(item.get("filter_id") or item.get("service_code") or "") for item in items}
    for otp_filter in repository.list_otp_filters():
        filter_id = str(otp_filter.get("filter_id") or otp_filter.get("service_code") or "")
        if filter_id and filter_id not in seen_filter_ids:
            items.append(
                {
                    "filter_id": filter_id,
                    "service_code": otp_filter.get("service_code") or filter_id,
                    "rule_name": otp_filter.get("rule_name") or filter_id,
                    "sender": otp_filter.get("sender_pattern") or "",
                    "code_masked": None,
                    "code": None,
                    "received_at": None,
                    "expires_at": None,
                    "status": "missing",
                    "source_type": "sms",
                    "source_id": None,
                    "otp_request_id": "",
                }
            )
    return {"ok": True, "items": items[:safe_limit]}


@admin_router.post("/otp/configurations")
def admin_save_otp_configuration(request: Request, payload: OtpConfigurationPayload) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.otp.manage")
    try:
        config = mobile_repository().save_otp_configuration(payload)
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service code da ton tai.") from error
    mobile_repository().base.add_audit_log(actor["username"], "mobile_otp_config_saved", f"Luu cau hinh OTP {payload.service_code}")
    return {"ok": True, "configuration": config}


@admin_router.post("/otp/test-regex")
def admin_test_otp_regex(request: Request, payload: OtpRegexTestPayload) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.otp.view")
    code = security.extract_otp(payload.sample_text, payload.otp_regex)
    return {"ok": True, "matched": bool(code), "code_masked": code, "code": code}


@admin_router.get("/otp/requests")
def admin_otp_requests(request: Request, limit: int = ADMIN_TABLE_PAGE_SIZE) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.otp.view")
    return {"ok": True, "requests": mobile_repository().list_otp_requests(admin_table_limit(limit))}


@admin_router.post("/otp/requests")
def admin_create_otp_request(request: Request, payload: OtpRequestCreatePayload) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.otp.manage")
    created = OtpService(mobile_repository()).create_request(payload.service_code, payload.job_id, payload.timeout_seconds)
    mobile_repository().base.add_audit_log(actor["username"], "mobile_otp_request_created", f"Tao OTP request {created.get('request_id')}")
    return {"ok": True, "request": created}


@admin_router.post("/otp/requests/{request_id}/cancel")
def admin_cancel_otp_request(request: Request, request_id: str) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.otp.manage")
    OtpService(mobile_repository()).cancel_request(request_id, "admin_cancelled")
    mobile_repository().base.add_audit_log(actor["username"], "mobile_otp_request_cancelled", f"Huy OTP request {request_id}")
    return {"ok": True}


@admin_router.get("/otp/events")
def admin_otp_events(request: Request, limit: int = ADMIN_TABLE_PAGE_SIZE) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.audit.view")
    return {"ok": True, "events": mobile_repository().list_otp_events(admin_table_limit(limit))}
