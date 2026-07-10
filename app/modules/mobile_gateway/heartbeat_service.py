from app.modules.mobile_gateway.repository import MobileGatewayRepository


class HeartbeatService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository
