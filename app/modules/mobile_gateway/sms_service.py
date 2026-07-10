from __future__ import annotations

from typing import Any

from app.modules.mobile_gateway.otp_service import OtpService
from app.modules.mobile_gateway.repository import MobileGatewayRepository
from app.modules.mobile_gateway.schemas import SmsMessageIn


class SmsService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository
        self.otp_service = OtpService(repository)

    def save_batch(self, device_id: str, messages: list[SmsMessageIn]) -> dict[str, Any]:
        inserted, skipped = self.repository.save_sms_messages(device_id, messages)
        matches = []
        for sms in inserted:
            matched = self.otp_service.match_incoming_sms(sms)
            if matched:
                matches.append(matched)
            else:
                latest = self.otp_service.record_latest_from_sms(sms)
                if latest:
                    matches.append(latest)
        return {"ok": True, "inserted": len(inserted), "skipped": skipped, "otp_matches": len(matches)}
