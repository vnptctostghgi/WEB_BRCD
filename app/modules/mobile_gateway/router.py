from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.data_access.repository_factory import build_repository
from app.modules.mobile_gateway import security
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
    OtpRegexTestPayload,
    OtpRequestCreatePayload,
    PairDevicePayload,
    SmsBatchPayload,
)
from app.modules.mobile_gateway.sms_service import SmsService
from app.settings import get_settings


router = APIRouter(prefix="/api/mobile-gateway", tags=["mobile-gateway"])
admin_router = APIRouter(prefix="/api/admin/mobile-gateway", tags=["admin-mobile-gateway"])


def mobile_repository() -> MobileGatewayRepository:
    settings = get_settings()
    return MobileGatewayRepository(build_repository(settings), settings)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else ""


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
    device = repository.get_device_record(device_id)
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
    repository.cleanup_nonces()
    if repository.nonce_exists(device_id, nonce):
        raise security.generic_auth_error()
    secret = repository.device_secret(device)
    canonical = "\n".join([request.method.upper(), request.url.path, timestamp, nonce, body_hash])
    if not secret or not security.verify_signature(secret, canonical, signature):
        raise security.generic_auth_error()
    repository.save_nonce(device_id, nonce, (now + timedelta(seconds=skew)).isoformat(timespec="seconds"))
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
    policy = context["repository"].get_policy(context["device_id"])
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
            "diagnostics_enabled": bool(policy.get("diagnostics_enabled")),
            "minimum_app_version": policy.get("minimum_app_version") or "1.1.0",
            "force_update": bool(policy.get("force_update")),
            "local_retention_days": policy.get("local_retention_days") or 14,
        },
    }


@router.get("/device/commands")
async def device_commands(context: dict[str, Any] = Depends(authenticated_device)) -> dict[str, Any]:
    commands = context["repository"].deliver_pending_commands(context["device_id"])
    return {"ok": True, "commands": commands}


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


@admin_router.get("/overview")
def admin_overview(request: Request) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.view")
    repository = mobile_repository()
    threshold = int(getattr(get_settings(), "mobile_gateway_online_threshold_seconds", 180) or 180)
    return {"ok": True, "overview": repository.overview_counts(threshold)}


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
        try:
            seen = datetime.fromisoformat(str(device.get("last_seen_at") or "").replace("Z", "+00:00"))
            online = bool(device.get("is_active")) and seen >= cutoff
        except ValueError:
            online = False
        devices.append({**device, "online": online, "heartbeat": heartbeat})
    return {"ok": True, "devices": devices}


@admin_router.post("/pairing-codes")
def admin_create_pairing_code(request: Request) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.devices.manage")
    result = PairingService(mobile_repository()).create_pairing_code(actor["username"])
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
def admin_sms(request: Request, page: int = 1, page_size: int = 50, device_id: str = "", sender: str = "", query: str = "", otp_only: bool = False) -> dict[str, Any]:
    user = require_mobile_permission(request, "mobile_gateway.sms.view")
    data = mobile_repository().list_sms(page=page, page_size=page_size, device_id=device_id, sender=sender, query=query, otp_only=otp_only)
    can_view_content = has_mobile_permission(user, "mobile_gateway.sms.view_content")
    if not has_mobile_permission(user, "mobile_gateway.sms.view_content"):
        for item in data["items"]:
            item["body"] = item.get("body_masked") or security.mask_otp_text(item.get("body") or "")
    elif can_view_content:
        for item in data["items"]:
            item["body"] = security.mask_otp_text(item.get("body") or item.get("body_masked") or "")
    return {"ok": True, **data}


@admin_router.get("/notifications")
def admin_notifications(request: Request, limit: int = 100) -> dict[str, Any]:
    user = require_mobile_permission(request, "mobile_gateway.notifications.view")
    items = mobile_repository().list_notifications(limit)
    if not has_mobile_permission(user, "mobile_gateway.notifications.view_content"):
        for item in items:
            item["text"] = item.get("text_masked") or security.mask_otp_text(item.get("text") or "")
    else:
        for item in items:
            item["text"] = security.mask_otp_text(item.get("text") or item.get("text_masked") or "")
    return {"ok": True, "items": items}


@admin_router.get("/commands")
def admin_commands(request: Request, device_id: str = "", limit: int = 100) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.commands.view")
    return {"ok": True, "commands": mobile_repository().list_commands(device_id=device_id, limit=limit)}


@admin_router.post("/commands")
def admin_create_command(request: Request, payload: AdminCommandPayload) -> dict[str, Any]:
    actor = require_mobile_permission(request, "mobile_gateway.commands.manage")
    command = mobile_repository().create_command(payload.device_id, payload.command_type, payload.payload, actor["username"], payload.ttl_seconds)
    mobile_repository().base.add_audit_log(actor["username"], "mobile_command_created", f"Gui lenh {payload.command_type} toi {payload.device_id}")
    return {"ok": True, "command": command}


@admin_router.get("/diagnostics")
def admin_diagnostics(request: Request, limit: int = 100) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.audit.view")
    return {"ok": True, "items": mobile_repository().list_diagnostics(limit)}


@admin_router.get("/otp/configurations")
def admin_otp_configurations(request: Request) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.otp.view")
    repository = mobile_repository()
    repository.ensure_defaults()
    return {"ok": True, "configurations": repository.list_otp_configurations()}


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
    return {"ok": True, "matched": bool(code), "code_masked": security.code_mask(code)}


@admin_router.get("/otp/requests")
def admin_otp_requests(request: Request, limit: int = 100) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.otp.view")
    return {"ok": True, "requests": mobile_repository().list_otp_requests(limit)}


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
def admin_otp_events(request: Request, limit: int = 100) -> dict[str, Any]:
    require_mobile_permission(request, "mobile_gateway.audit.view")
    return {"ok": True, "events": mobile_repository().list_otp_events(limit)}
