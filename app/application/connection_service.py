from typing import Any

import httpx

from app.application.database_service import DatabaseService
from app.application.google_drive_service import test_google_drive_connection
from app.application.telegram_notifier import TelegramNotifier
from app.application.zalo_bot import ZaloBotClient
from app.data_access.internal_api_client import InternalApiClient
from app.modules.internal_email.service import test_internal_email_connection
from app.settings import Settings


class ConnectionService:
    def __init__(self, repository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def seed_current_connections(self) -> None:
        existing_internal = self.repository.get_system_connection_by_code("internal_fastapi_api") or {}
        existing_internal_config = existing_internal.get("config") if isinstance(existing_internal.get("config"), dict) else {}
        internal_url = existing_internal_config.get("url") or self.settings.internal_api_url
        internal_mock_mode = existing_internal_config.get("mock_mode", self.settings.internal_api_mock_mode)
        internal_config = {
            "url": internal_url,
            "mock_mode": internal_mock_mode,
            "secret_ref": "INTERNAL_API_TOKEN",
            **existing_internal_config,
        }
        self.repository.upsert_system_connection(
            code="internal_fastapi_api",
            name="API dữ liệu nội bộ",
            connection_type="internal_api",
            description="Máy chủ FastAPI nội bộ nhận SQL được cấu hình trên web và truy vấn DB cơ quan.",
            config=internal_config,
            is_active=bool(existing_internal.get("is_active") if existing_internal else internal_url),
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
        existing_drive = self.repository.get_system_connection_by_code("drive_storage") or {}
        existing_drive_config = existing_drive.get("config") if isinstance(existing_drive.get("config"), dict) else {}
        self.repository.upsert_system_connection(
            code="drive_storage",
            name=str(existing_drive.get("name") or "Google Drive"),
            connection_type="drive",
            description="Kết nối Drive/Cloud storage. Chưa cấu hình OAuth hoặc service account.",
            config={"provider": "", "folder": "", "secret_ref": "DRIVE_SECRET", **existing_drive_config},
            is_active=bool(existing_drive.get("is_active") or existing_drive_config.get("oauth_refresh_token_enc")),
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
        self.repository.upsert_system_connection(
            code="zalo_bot",
            name="Zalo Bot",
            connection_type="zalo",
            description="Nhan va gui thong bao qua Zalo Bot Platform bang webhook HTTPS.",
            config={
                "webhook_url": self.settings.zalo_webhook_url,
                "webhook_path": "/api/zalo/webhook",
                "token_ref": "ZALO_BOT_TOKEN",
                "secret_ref": "ZALO_WEBHOOK_SECRET",
            },
            is_active=bool(
                self.settings.zalo_bot_token.get_secret_value()
                and self.settings.zalo_webhook_url
                and self.settings.zalo_webhook_secret.get_secret_value()
            ),
        )
        existing_email = self.repository.get_system_connection_by_code("internal_email") or {}
        existing_email_config = existing_email.get("config") if isinstance(existing_email.get("config"), dict) else {}
        email_username = existing_email_config.get("username") or self.settings.internal_email_username
        email_config = {
            "host": existing_email_config.get("host") or self.settings.internal_email_host,
            "port": existing_email_config.get("port") or self.settings.internal_email_port,
            "use_ssl": existing_email_config.get("use_ssl", True),
            "username": email_username,
            "password_env": existing_email_config.get("password_env") or "INTERNAL_EMAIL_PASSWORD",
            "mailbox": existing_email_config.get("mailbox") or self.settings.internal_email_mailbox,
            "lookback_minutes": existing_email_config.get("lookback_minutes") or self.settings.internal_email_lookback_minutes,
            "max_messages": existing_email_config.get("max_messages") or self.settings.internal_email_max_messages,
            "timeout_seconds": existing_email_config.get("timeout_seconds") or self.settings.internal_email_timeout_seconds,
            "secret_ref": "INTERNAL_EMAIL_PASSWORD",
            **existing_email_config,
        }
        self.repository.upsert_system_connection(
            code="internal_email",
            name=str(existing_email.get("name") or "Email noi bo VNPT"),
            connection_type="internal_email",
            description="Dong bo hop thu noi bo qua IMAP de phat hien OTP tu email.vnpt.vn.",
            config=email_config,
            is_active=bool(
                existing_email.get("is_active")
                or (
                    self.settings.internal_email_sync_enabled
                    and email_username
                    and self.settings.internal_email_password.get_secret_value()
                )
            ),
        )

    def test_connection(self, code: str) -> dict[str, Any]:
        connection = self.repository.get_system_connection_by_code(code)
        if not connection:
            raise ValueError("Không tìm thấy kết nối.")

        if connection["connection_type"] == "internal_api":
            service = DatabaseService(InternalApiClient(self.settings, connection), self.repository)
            return self._with_connection(service.get_connection_status(), connection)

        if connection["connection_type"] == "supabase":
            return self._with_connection(self._test_supabase(), connection)

        if connection["connection_type"] == "telegram":
            return self._with_connection(TelegramNotifier(self.settings).test(), connection)

        if connection["connection_type"] == "zalo":
            return self._with_connection(ZaloBotClient(self.settings).test(), connection)

        if connection["connection_type"] == "drive":
            return self._with_connection(test_google_drive_connection(self.settings, self.repository), connection)

        if connection["connection_type"] == "internal_email":
            return self._with_connection(test_internal_email_connection(self.settings, self.repository, connection), connection)

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
