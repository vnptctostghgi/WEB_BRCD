import logging
from typing import Any

import oracledb

from app.data_access.oracle_repository import OracleRepository


logger = logging.getLogger(__name__)


class DatabaseService:
    """Application Layer: xử lý nghiệp vụ và ẩn lỗi kỹ thuật khỏi giao diện."""

    def __init__(self, repository: OracleRepository) -> None:
        self.repository = repository

    def get_connection_status(self) -> dict[str, Any]:
        try:
            details = self.repository.check_connection()
            return {
                "ok": True,
                "message": "Kết nối Database thành công.",
                "details": details,
            }
        except ValueError as error:
            logger.exception("Oracle config invalid: %s", error)
            return {
                "ok": False,
                "message": "Thiếu cấu hình kết nối Oracle.",
                "details": None,
            }
        except oracledb.Error as error:
            logger.exception("Cannot connect Oracle: %s", error)
            return {
                "ok": False,
                "message": self._oracle_error_message(str(error)),
                "details": None,
            }

    @staticmethod
    def _oracle_error_message(raw_error: str) -> str:
        lowered = raw_error.lower()
        if "timed out" in lowered or "timeout" in lowered:
            return "Oracle phản hồi quá lâu."
        if "invalid username/password" in lowered or "ora-01017" in lowered:
            return "Sai tài khoản hoặc mật khẩu Oracle."
        if "listener" in lowered or "ora-12514" in lowered or "ora-12541" in lowered:
            return "Không kết nối được listener Oracle."
        return "Không kết nối được DB cơ quan Oracle."
