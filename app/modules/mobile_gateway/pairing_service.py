from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.modules.mobile_gateway import security
from app.modules.mobile_gateway.exceptions import PairingError
from app.modules.mobile_gateway.repository import MobileGatewayRepository
from app.modules.mobile_gateway.schemas import PairDevicePayload


class PairingService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository

    def create_pairing_code(self, created_by: str, policy_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.repository.expire_pairing_codes()
        code = security.generate_pairing_code()
        code_hash = security.pairing_code_hash(self.repository.settings, code)
        configured_ttl = int(getattr(self.repository.settings, "mobile_gateway_pairing_ttl_seconds", 0) or 0)
        ttl_seconds = configured_ttl if configured_ttl > 0 else 10 * 365 * 24 * 60 * 60
        row = self.repository.create_pairing_code(
            code_hash,
            created_by,
            ttl_seconds,
            policy_payload or {},
        )
        return {
            "ok": True,
            "id": row.get("id"),
            "pairing_code": code,
            "expires_at": row.get("expires_at"),
            "ttl_seconds": max(0, configured_ttl),
            "no_expiry": configured_ttl <= 0,
            "message": "Ma ghep noi da duoc tao.",
        }

    def pair_device(self, payload: PairDevicePayload, ip_address: str) -> dict[str, Any]:
        code_hash = security.pairing_code_hash(self.repository.settings, payload.pairing_code)
        pairing = self.repository.get_pairing_code_by_hash(code_hash)
        if not pairing or pairing.get("status") != "active":
            raise PairingError("Ma ghep noi khong hop le hoac da duoc su dung.")
        expires_at = str(pairing.get("expires_at") or "")
        try:
            if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now().astimezone():
                raise PairingError("Ma ghep noi da het han.")
        except ValueError as error:
            raise PairingError("Ma ghep noi khong hop le.") from error
        device_id = str(uuid.uuid4())
        device_secret = security.generate_device_secret()
        encrypted_secret = security.encrypt_text(self.repository.settings, device_secret, "mobile")
        device = self.repository.create_device(
            {
                **payload.model_dump(),
                "device_id": device_id,
                "name": payload.device_name or payload.model or "Android Gateway",
                "encrypted_device_secret": encrypted_secret,
                "last_ip": ip_address,
                "created_by": pairing.get("created_by") or "",
            }
        )
        policy_payload = self.repository._json_loads(pairing.get("policy_payload"), {})
        base_policy = self.repository.default_policy(device_id)
        policy = {
            **base_policy,
            "sms_enabled": bool(policy_payload.get("sms_enabled", base_policy["sms_enabled"])),
            "notifications_enabled": bool(policy_payload.get("notifications_enabled", base_policy["notifications_enabled"])),
            "clipboard_enabled": bool(policy_payload.get("clipboard_enabled", base_policy["clipboard_enabled"])),
            "camera_enabled": bool(policy_payload.get("camera_enabled", base_policy["camera_enabled"])),
            "diagnostics_enabled": bool(policy_payload.get("heartbeat_enabled", True)),
        }
        self.repository.save_policy(device_id, policy, "system")
        self.repository.mark_pairing_used(int(pairing["id"]), device_id)
        return {
            "ok": True,
            "device_id": device["device_id"],
            "device_secret": device_secret,
            "message": "Ghep noi thanh cong",
        }
