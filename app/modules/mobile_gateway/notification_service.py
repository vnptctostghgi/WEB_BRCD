from __future__ import annotations

from typing import Any

from app.modules.mobile_gateway.otp_service import OtpService
from app.modules.mobile_gateway.repository import MobileGatewayRepository
from app.modules.mobile_gateway.schemas import NotificationIn


class NotificationService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository
        self.otp_service = OtpService(repository)

    def save_batch(self, device_id: str, notifications: list[NotificationIn]) -> dict[str, Any]:
        inserted, skipped = self.repository.save_notifications(device_id, notifications)
        matches = []
        for notification in inserted:
            matched = self.otp_service.match_incoming_notification(notification)
            if matched:
                matches.append(matched)
        return {"ok": True, "inserted": len(inserted), "skipped": skipped, "otp_matches": len(matches)}
