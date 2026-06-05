import logging
from datetime import datetime
from typing import Any

import httpx

from app.settings import Settings


logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.token = settings.telegram_token.get_secret_value() or settings.bot_token.get_secret_value()
        self.chat_id = settings.my_telegram_id

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, title: str, message: str, details: dict[str, Any] | None = None) -> bool:
        if not self.enabled:
            return False
        lines = [
            f"Canh bao: {title}",
            f"Ung dung: {self.settings.app_name}",
            f"Moi truong: {self.settings.app_env}",
            f"Thoi gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            message,
        ]
        if details:
            safe_details = "\n".join(f"- {key}: {value}" for key, value in details.items())
            lines.extend(["", safe_details])
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": "\n".join(lines),
                        "disable_web_page_preview": True,
                    },
                )
            if response.status_code >= 400:
                logger.warning("Telegram send failed: %s %s", response.status_code, response.text[:300])
                return False
            return True
        except Exception:
            logger.exception("Telegram send failed")
            return False

    def test(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "ok": False,
                "message": "Chưa cấu hình token hoặc chat ID Telegram.",
                "details": {"bot": self.settings.bot_username},
            }
        try:
            with httpx.Client(timeout=15) as client:
                response = client.get(f"https://api.telegram.org/bot{self.token}/getMe")
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "message": "Token Telegram không hợp lệ hoặc Bot API không phản hồi.",
                    "details": {"status_code": response.status_code, "bot": self.settings.bot_username},
                }
            data = response.json()
            return {
                "ok": bool(data.get("ok")),
                "message": "Kết nối Telegram thành công.",
                "details": {"bot": self.settings.bot_username},
            }
        except httpx.TimeoutException:
            return {
                "ok": False,
                "message": "Telegram phản hồi quá lâu.",
                "details": {"bot": self.settings.bot_username},
            }
        except httpx.RequestError:
            return {
                "ok": False,
                "message": "Không kết nối được Telegram Bot API.",
                "details": {"bot": self.settings.bot_username},
            }
