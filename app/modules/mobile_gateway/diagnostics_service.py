from app.modules.mobile_gateway.repository import MobileGatewayRepository


class DiagnosticsService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository
