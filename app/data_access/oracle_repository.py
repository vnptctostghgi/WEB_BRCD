from datetime import datetime
from typing import Any

import oracledb

from app.settings import Settings


class OracleRepository:
    """Data Access Layer: noi duy nhat truc tiep lam viec voi Oracle."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check_connection(self) -> dict[str, Any]:
        if self.settings.db_mock_mode:
            return {
                "database_time": datetime.now().isoformat(timespec="seconds"),
                "database_version": "Mock Oracle 0.1",
                "mode": "mock",
            }

        self._validate_configuration()
        dsn = oracledb.makedsn(
            self.settings.db_host,
            self.settings.db_port,
            service_name=self.settings.db_service,
        )

        with oracledb.connect(
            user=self.settings.db_user,
            password=self.settings.db_pass.get_secret_value(),
            dsn=dsn,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT SYSDATE AS SERVER_TIME FROM DUAL")
                database_time = cursor.fetchone()[0]

            return {
                "database_time": str(database_time),
                "database_version": connection.version,
                "mode": "oracle",
            }

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
