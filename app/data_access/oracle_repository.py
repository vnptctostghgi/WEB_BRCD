from typing import Any

from app.application.oracle_pool import oracle_pool_service
from app.settings import Settings


class OracleRepository:
    """Data Access Layer: noi duy nhat truc tiep lam viec voi Oracle."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check_connection(self) -> dict[str, Any]:
        oracle_pool_service.configure(self.settings)
        return oracle_pool_service.check_connection()

    def select_paginated(self, sql: str, binds: dict[str, Any] | None = None, page: int = 1, page_size: int = 50) -> list[dict[str, Any]]:
        oracle_pool_service.configure(self.settings)
        return oracle_pool_service.execute_paginated_select(sql, binds, page, page_size)

    def _validate_configuration(self) -> None:
        required_values = {
            "DB_HOST": self.settings.db_host,
            "DB_SERVICE": self.settings.db_service,
            "DB_USER": self.settings.db_user,
            "DB_PASS": self.settings.db_pass.get_secret_value(),
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise ValueError(f"Thieu cau hinh: {', '.join(missing)}")
