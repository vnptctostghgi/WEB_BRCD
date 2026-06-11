from typing import Any

import httpx

from app.application.database_service import DatabaseService
from app.application.telegram_notifier import TelegramNotifier
from app.data_access.internal_api_client import InternalApiClient
from app.settings import Settings


class ConnectionService:
    def __init__(self, repository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def seed_current_connections(self) -> None:
        self.repository.upsert_system_connection(
            code="internal_fastapi_api",
            name="API dữ liệu nội bộ",
            connection_type="internal_api",
            description="Máy chủ FastAPI nội bộ nhận SQL được cấu hình trên web và truy vấn DB cơ quan.",
            config={
                "url": self.settings.internal_api_url,
                "mock_mode": self.settings.internal_api_mock_mode,
                "secret_ref": "INTERNAL_API_TOKEN",
            },
            is_active=bool(self.settings.internal_api_url),
        )
        self.repository.upsert_system_connection(
            code="supabase_web_db",
            name="DB của web Supabase",
            connection_type="supabase",
            description="Database chính của ứng dụng quản trị web.",
            config={
                "rest_url": self.settings.supabase_rest_url,
                "backend": self.settings.app_database_backend,
                "secret_ref": "SUPABASE_SECRET_KEY",
            },
            is_active=self.settings.app_database_backend == "supabase",
        )
        self.repository.upsert_system_connection(
            code="ftp_storage",
            name="FTP",
            connection_type="ftp",
            description="Kết nối FTP phục vụ trao đổi file. Chưa cấu hình thông tin máy chủ.",
            config={"host": "", "port": 21, "secret_ref": "FTP_PASSWORD"},
            is_active=False,
        )
        self.repository.upsert_system_connection(
            code="drive_storage",
            name="Drive",
            connection_type="drive",
            description="Kết nối Drive/Cloud storage. Chưa cấu hình OAuth hoặc service account.",
            config={"provider": "", "folder": "", "secret_ref": "DRIVE_SECRET"},
            is_active=False,
        )
        self.repository.upsert_system_connection(
            code="telegram_bot",
            name="Telegram Bot cảnh báo",
            connection_type="telegram",
            description="Gửi cảnh báo khi web lỗi hoặc mất kết nối hệ thống.",
            config={
                "bot_username": self.settings.bot_username,
                "chat_id": self.settings.my_telegram_id,
                "secret_ref": "TELEGRAM_TOKEN",
            },
            is_active=bool(self.settings.telegram_token.get_secret_value() and self.settings.my_telegram_id),
        )

    def test_connection(self, code: str) -> dict[str, Any]:
        connection = self.repository.get_system_connection_by_code(code)
        if not connection:
            raise ValueError("Không tìm thấy kết nối.")

        if connection["connection_type"] == "internal_api":
            service = DatabaseService(InternalApiClient(self.settings), self.repository)
            return self._with_connection(service.get_connection_status(), connection)

        if connection["connection_type"] == "supabase":
            return self._with_connection(self._test_supabase(), connection)

        if connection["connection_type"] == "telegram":
            return self._with_connection(TelegramNotifier(self.settings).test(), connection)

        return self._with_connection(
            {
                "ok": False,
                "message": f"{connection['name']} chưa có đủ cấu hình để kiểm tra.",
                "details": {"type": connection["connection_type"]},
            },
            connection,
        )

    def _test_supabase(self) -> dict[str, Any]:
        if not self.settings.supabase_rest_url or not self.settings.supabase_secret_key.get_secret_value():
            return {"ok": False, "message": "Chưa cấu hình URL hoặc secret key Supabase.", "details": None}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get(
                    f"{self.settings.supabase_rest_url.rstrip('/')}/features",
                    params={"select": "code", "limit": "1"},
                    headers={"apikey": self.settings.supabase_secret_key.get_secret_value()},
                )
            if response.status_code < 400:
                return {
                    "ok": True,
                    "message": "Kết nối Supabase thành công.",
                    "details": {"status_code": response.status_code},
                }
            return {
                "ok": False,
                "message": self._supabase_error_message(response.status_code),
                "details": {"status_code": response.status_code},
            }
        except httpx.TimeoutException:
            return {"ok": False, "message": "Supabase phản hồi quá lâu.", "details": None}
        except httpx.RequestError:
            return {"ok": False, "message": "Không kết nối được Supabase REST API.", "details": None}

    @staticmethod
    def _supabase_error_message(status_code: int) -> str:
        if status_code in {401, 403}:
            return "Supabase từ chối truy cập. Kiểm tra lại secret key."
        if status_code == 404:
            return "Không tìm thấy bảng hoặc endpoint Supabase."
        if status_code >= 500:
            return "Supabase đang lỗi máy chủ."
        return f"Supabase trả lỗi HTTP {status_code}."

    @staticmethod
    def _with_connection(result: dict[str, Any], connection: dict[str, Any]) -> dict[str, Any]:
        result["connection_code"] = connection["code"]
        result["connection_name"] = connection["name"]
        return result
