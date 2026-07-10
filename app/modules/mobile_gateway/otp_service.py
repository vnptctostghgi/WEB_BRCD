from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

from app.modules.mobile_gateway import security
from app.modules.mobile_gateway.exceptions import OtpServiceError
from app.modules.mobile_gateway.repository import MobileGatewayRepository


class OtpService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository

    def create_request(self, service_code: str, job_id: str = "", timeout_seconds: int | None = None) -> dict[str, Any]:
        service_code = str(service_code or "").strip().lower()
        if not service_code:
            raise OtpServiceError("service_code is required")
        config = self.repository.get_otp_configuration(service_code)
        if not config:
            if service_code == "onebss":
                self.repository.ensure_defaults()
                config = self.repository.get_otp_configuration(service_code)
        if not config or not config.get("enabled"):
            raise OtpServiceError(f"OTP configuration is disabled or missing: {service_code}")
        return self.repository.create_otp_request(service_code, job_id, config, timeout_seconds)

    def wait_for_code(self, request_id: str, timeout_seconds: int, poll_seconds: float = 2.0) -> str:
        deadline = time.monotonic() + max(1, int(timeout_seconds or 1))
        while time.monotonic() <= deadline:
            self.repository.expire_otp_requests()
            request = self.repository.get_otp_request(request_id)
            if not request:
                return ""
            if request.get("status") == "matched":
                return self.repository.consume_otp_request(request_id)
            if request.get("status") not in {"waiting", "matched"}:
                return ""
            time.sleep(max(0.5, poll_seconds))
        self.repository.cancel_otp_request(request_id, "timeout")
        return ""

    def consume_code(self, request_id: str) -> str:
        return self.repository.consume_otp_request(request_id)

    def cancel_request(self, request_id: str, reason: str = "cancelled") -> None:
        self.repository.cancel_otp_request(request_id, reason)

    def expire_requests(self) -> int:
        return self.repository.expire_otp_requests()

    def match_incoming_sms(self, sms: dict[str, Any]) -> dict[str, Any] | None:
        if sms.get("otp_request_id"):
            return None
        body = str(sms.get("body") or "")
        if not body:
            return None
        for request in self.repository.waiting_otp_requests():
            config = self.repository.get_otp_configuration(str(request.get("service_code") or ""))
            if not config or not config.get("enabled"):
                continue
            if config.get("source_type") not in {"sms", "both"}:
                continue
            if not self._source_time_allowed(request, sms.get("received_at")):
                continue
            if not self._device_allowed(config, sms):
                continue
            if not self._sender_allowed(config, str(sms.get("normalized_sender") or sms.get("sender") or "")):
                continue
            code = security.extract_otp(
                body,
                str(config.get("otp_regex") or ""),
                int(config.get("otp_length_min") or 4),
                int(config.get("otp_length_max") or 8),
                str(config.get("otp_keyword") or ""),
            )
            if not code:
                continue
            if self.repository.match_otp_request(str(request["request_id"]), "sms", sms["id"], code):
                self.repository.mark_sms_matched(sms["id"], str(request["request_id"]), used=False)
                return {"request_id": request["request_id"], "code_masked": security.code_mask(code)}
        return None

    def match_incoming_notification(self, notification: dict[str, Any]) -> dict[str, Any] | None:
        if notification.get("otp_request_id"):
            return None
        text = f"{notification.get('title') or ''}\n{notification.get('text') or ''}"
        for request in self.repository.waiting_otp_requests():
            config = self.repository.get_otp_configuration(str(request.get("service_code") or ""))
            if not config or not config.get("enabled"):
                continue
            if config.get("source_type") not in {"notification", "both"}:
                continue
            if not self._source_time_allowed(request, notification.get("posted_at")):
                continue
            if not self._device_allowed(config, notification):
                continue
            if config.get("package_pattern") and config["package_pattern"].lower() not in str(notification.get("package_name") or "").lower():
                continue
            if config.get("title_pattern") and config["title_pattern"].lower() not in str(notification.get("title") or "").lower():
                continue
            code = security.extract_otp(
                text,
                str(config.get("otp_regex") or ""),
                int(config.get("otp_length_min") or 4),
                int(config.get("otp_length_max") or 8),
                str(config.get("otp_keyword") or ""),
            )
            if not code:
                continue
            if self.repository.match_otp_request(str(request["request_id"]), "notification", notification["id"], code):
                self.repository.mark_notification_matched(notification["id"], str(request["request_id"]), used=False)
                return {"request_id": request["request_id"], "code_masked": security.code_mask(code)}
        return None

    @staticmethod
    def _dt(value: Any) -> datetime | None:
        try:
            return datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return None

    def _source_time_allowed(self, request: dict[str, Any], source_time: Any) -> bool:
        source_dt = self._dt(source_time)
        requested_at = self._dt(request.get("requested_at"))
        expires_at = self._dt(request.get("expires_at"))
        if not source_dt or not requested_at or not expires_at:
            return False
        return requested_at <= source_dt <= expires_at

    @staticmethod
    def _device_allowed(config: dict[str, Any], source: dict[str, Any]) -> bool:
        configured_device = str(config.get("device_id") or "").strip()
        if configured_device and configured_device != str(source.get("device_id") or ""):
            return False
        configured_sim = config.get("sim_slot")
        if configured_sim is not None and configured_sim != "":
            try:
                if int(configured_sim) != int(source.get("sim_slot")):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _sender_allowed(config: dict[str, Any], normalized_sender: str) -> bool:
        pattern = str(config.get("sender_pattern") or "").strip()
        if not pattern:
            return True
        sender = security.normalize_sender(normalized_sender)
        wanted = security.normalize_sender(pattern)
        match_type = str(config.get("sender_match_type") or "contains")
        if match_type == "equals":
            return sender == wanted
        if match_type == "regex":
            try:
                return bool(re.search(pattern, normalized_sender, re.IGNORECASE))
            except re.error:
                return False
        return wanted in sender
