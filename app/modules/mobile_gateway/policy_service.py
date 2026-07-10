from app.modules.mobile_gateway.repository import MobileGatewayRepository


class PolicyService:
    def __init__(self, repository: MobileGatewayRepository) -> None:
        self.repository = repository
