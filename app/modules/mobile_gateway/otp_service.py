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
            if not config and self.repository.list_otp_filters(service_code=service_code, enabled_only=True):
                config = {
                    "id": None,
                    "service_code": service_code,
                    "enabled": True,
                    "source_type": "sms",
                    "wait_timeout_seconds": timeout_seconds or 120,
                }
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
            self.match_latest_for_request(request)
            request = self.repository.get_otp_request(request_id)
            if request and request.get("status") == "matched":
                return self.repository.consume_otp_request(request_id)
            if request.get("status") not in {"waiting", "matched"}:
                return ""
            time.sleep(max(0.5, poll_seconds))
        self.repository.cancel_otp_request(request_id, "timeout")
        return ""

    def consume_code(self, request_id: str) -> str:
        request = self.repository.get_otp_request(request_id)
        if request and request.get("status") == "waiting":
            self.match_latest_for_request(request)
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
            if not self._source_time_allowed(request, sms.get("received_at")):
                continue
            for otp_filter in self._filters_for_request(request):
                if not otp_filter.get("enabled", True):
                    continue
                if otp_filter.get("source_type") and otp_filter.get("source_type") not in {"sms", "both"}:
                    continue
                if not self._device_allowed(otp_filter, sms):
                    continue
                if not self._sender_allowed(otp_filter, str(sms.get("normalized_sender") or sms.get("sender") or "")):
                    continue
                code = self._extract_code_for_filter(body, otp_filter)
                if not code:
                    continue
                if self.repository.match_otp_request(str(request["request_id"]), "sms", sms["id"], code):
                    self.repository.mark_sms_matched(sms["id"], str(request["request_id"]), used=False)
                    self.repository.record_otp_latest(
                        otp_filter=otp_filter,
                        sender=str(sms.get("sender") or ""),
                        code=code,
                        received_at=str(sms.get("received_at") or ""),
                        source_type="sms",
                        source_id=sms["id"],
                        request_id=str(request["request_id"]),
                    )
                    return {"request_id": request["request_id"], "code_masked": security.code_mask(code)}
        return None

    def record_latest_from_sms(self, sms: dict[str, Any]) -> dict[str, Any] | None:
        if sms.get("otp_request_id"):
            return None
        body = str(sms.get("body") or "")
        if not body:
            return None
        filters = self.repository.list_otp_filters(enabled_only=True)
        if not filters:
            self.repository.ensure_defaults()
            filters = self.repository.list_otp_filters(enabled_only=True)
        for otp_filter in filters:
            if not self._device_allowed(otp_filter, sms):
                continue
            if not self._sender_allowed(otp_filter, str(sms.get("normalized_sender") or sms.get("sender") or "")):
                continue
            code = self._extract_code_for_filter(body, otp_filter)
            if not code:
                continue
            self.repository.record_otp_latest(
                otp_filter=otp_filter,
                sender=str(sms.get("sender") or ""),
                code=code,
                received_at=str(sms.get("received_at") or ""),
                source_type="sms",
                source_id=sms["id"],
                request_id="",
            )
            return {"filter_id": otp_filter.get("filter_id"), "code": code}
        return None

    def match_latest_for_request(self, request: dict[str, Any] | str) -> dict[str, Any] | None:
        if isinstance(request, str):
            request = self.repository.get_otp_request(request) or {}
        request_id = str(request.get("request_id") or "").strip()
        service_code = str(request.get("service_code") or "").strip().lower()
        if not request_id or not service_code or request.get("status") != "waiting":
            return None
        self.repository.expire_otp_latest_values()
        for latest in self.repository.list_otp_latest_values(limit=100):
            if str(latest.get("service_code") or "").strip().lower() != service_code:
                continue
            if str(latest.get("status") or "").lower() != "valid":
                continue
            existing_request_id = str(latest.get("otp_request_id") or "").strip()
            if existing_request_id and existing_request_id != request_id:
                continue
            code = re.sub(r"\D+", "", str(latest.get("code_masked") or ""))
            if not code:
                continue
            if self.repository.match_otp_request(
                request_id,
                str(latest.get("source_type") or "latest"),
                str(latest.get("source_id") or latest.get("id") or ""),
                code,
            ):
                latest_id = latest.get("id")
                if latest_id is not None:
                    self.repository.bind_otp_latest_to_request(latest_id, request_id)
                source_type = str(latest.get("source_type") or "")
                source_id = str(latest.get("source_id") or "")
                if source_type == "sms" and source_id:
                    self.repository.mark_sms_matched(source_id, request_id, used=False)
                if source_type == "notification" and source_id:
                    self.repository.mark_notification_matched(source_id, request_id, used=False)
                return {"request_id": request_id, "code_masked": security.code_mask(code), "source_type": source_type, "source_id": source_id}
        return None

    def rematch_latest_for_filter(self, otp_filter: dict[str, Any]) -> dict[str, Any] | None:
        if not otp_filter or not otp_filter.get("enabled", True):
            return None
        for sms in self.repository.latest_sms_messages(limit=300):
            body = str(sms.get("body") or "")
            if not body:
                continue
            if not self._device_allowed(otp_filter, sms):
                continue
            if not self._sender_allowed(otp_filter, str(sms.get("normalized_sender") or sms.get("sender") or "")):
                continue
            code = self._extract_code_for_filter(body, otp_filter)
            if not code:
                continue
            self.repository.record_otp_latest(
                otp_filter=otp_filter,
                sender=str(sms.get("sender") or ""),
                code=code,
                received_at=str(sms.get("received_at") or ""),
                source_type="sms",
                source_id=sms["id"],
                request_id="",
            )
            return {
                "filter_id": otp_filter.get("filter_id"),
                "sender": sms.get("sender") or "",
                "code": code,
                "received_at": sms.get("received_at") or "",
            }
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

    def _filters_for_request(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        service_code = str(request.get("service_code") or "").strip().lower()
        filters = self.repository.list_otp_filters(service_code=service_code, enabled_only=True)
        if filters:
            return filters
        config = self.repository.get_otp_configuration(service_code)
        if not config or not config.get("enabled"):
            return []
        return [self._filter_from_config(config)]

    @staticmethod
    def _filter_from_config(config: dict[str, Any]) -> dict[str, Any]:
        return {
            "filter_id": str(config.get("service_code") or ""),
            "rule_name": str(config.get("service_name") or config.get("service_code") or ""),
            "service_code": str(config.get("service_code") or ""),
            "source_type": str(config.get("source_type") or "sms"),
            "sender_pattern": str(config.get("sender_pattern") or ""),
            "sender_match_type": "exact" if str(config.get("sender_match_type") or "") == "equals" else str(config.get("sender_match_type") or "contains"),
            "otp_regex": str(config.get("otp_regex") or r"(?<!\d)(\d{4,8})(?!\d)"),
            "otp_keyword": str(config.get("otp_keyword") or ""),
            "otp_length_min": int(config.get("otp_length_min") or 4),
            "otp_length_max": int(config.get("otp_length_max") or 8),
            "validity_seconds": int(config.get("validity_seconds") or 180),
            "device_id": str(config.get("device_id") or ""),
            "sim_slot": config.get("sim_slot"),
            "enabled": bool(config.get("enabled")),
        }

    @staticmethod
    def _extract_code_for_filter(text: str, otp_filter: dict[str, Any]) -> str:
        start_value = str(otp_filter.get("start_prefix") or "").strip()
        search_text = str(text or "")
        otp_length = int(otp_filter.get("otp_length") or 0)
        if start_value and re.fullmatch(r"\d+", start_value):
            start_index = max(0, int(start_value))
            if start_index >= len(search_text):
                return ""
            search_text = search_text[start_index:]
            if otp_length > 0:
                candidate = search_text[:otp_length] if len(search_text) >= otp_length else ""
                if candidate.isdigit():
                    return candidate
                match = re.search(rf"(?<!\d)(\d{{{otp_length}}})(?!\d)", search_text)
                return match.group(1) if match else ""
            match = re.search(r"\d+", search_text)
            return match.group(0) if match else ""
        if otp_length > 0:
            if start_value:
                if len(start_value) > otp_length:
                    return ""
                match = re.search(rf"(?<!\d)({re.escape(start_value)}\d{{{otp_length - len(start_value)}}})(?!\d)", search_text)
            else:
                match = re.search(rf"(?<!\d)(\d{{{otp_length}}})(?!\d)", search_text)
            return match.group(1) if match else ""
        if start_value:
            match = re.search(rf"(?<!\d)({re.escape(start_value)}\d+)(?!\d)", search_text)
            return match.group(1) if match else ""
        return security.extract_otp(
            search_text,
            str(otp_filter.get("otp_regex") or r"(?<!\d)(\d{4,8})(?!\d)"),
            int(otp_filter.get("otp_length_min") or 4),
            int(otp_filter.get("otp_length_max") or 8),
            str(otp_filter.get("otp_keyword") or ""),
        )

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
        if match_type in {"equals", "exact"}:
            return sender == wanted
        if match_type == "regex":
            try:
                return bool(re.search(pattern, normalized_sender, re.IGNORECASE))
            except re.error:
                return False
        return wanted in sender
