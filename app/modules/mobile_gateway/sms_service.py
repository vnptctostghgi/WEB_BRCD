from __future__ import annotations

from typing import Any

from app.modules.mobile_gateway import security
from app.modules.mobile_gateway.event_bus import mobile_gateway_events
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
        inserted_external_ids = {str(sms.get("external_id") or "") for sms in inserted}
        for sms in inserted:
            matched = self.otp_service.match_incoming_sms(sms)
            if matched:
                matches.append(matched)
            else:
                latest = self.otp_service.record_latest_from_sms(sms)
                if latest:
                    matches.append(latest)
        if skipped:
            for message in messages:
                if str(message.external_id or "") in inserted_external_ids:
                    continue
                latest = self.otp_service.record_latest_from_sms(
                    {
                        "id": message.external_id,
                        "device_id": device_id,
                        "external_id": message.external_id,
                        "sender": message.sender,
                        "normalized_sender": security.normalize_sender(message.sender),
                        "body": message.body or "",
                        "received_at": self.repository.time_text(message.received_at),
                        "sim_slot": message.sim_slot,
                    }
                )
                if latest:
                    matches.append(latest)
        if messages:
            mobile_gateway_events.publish(
                "sms_batch",
                {
                    "device_id": device_id,
                    "received": len(messages),
                    "inserted": len(inserted),
                    "skipped": skipped,
                    "otp_matches": len(matches),
                },
            )
        return {"ok": True, "inserted": len(inserted), "skipped": skipped, "otp_matches": len(matches)}
