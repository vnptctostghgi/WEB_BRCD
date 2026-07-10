from __future__ import annotations

from app.modules.mobile_gateway.repository import MobileGatewayRepository


class DeviceService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository

    def revoke(self, device_id: str) -> None:
        now = self.repository.now()
        self.repository.update_device(device_id, {"is_active": False, "revoked_at": now})

    def reactivate(self, device_id: str) -> None:
        self.repository.update_device(device_id, {"is_active": True, "revoked_at": None})
