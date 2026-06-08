import logging
from datetime import datetime
from typing import Any

import httpx

from app.settings import Settings


logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Gui thong bao Telegram duy nhat den MY_TELEGRAM_ID cua quan tri vien."""

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
            lines.append("")
            lines.extend(f"- {key}: {value}" for key, value in details.items())
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
            body = response.json()
            return bool(body.get("ok", True))
        except Exception:
            logger.exception("Telegram send failed")
            return False

    def send_task_reminder(self, task: dict[str, Any]) -> bool:
        return self.send_message(
            "Nhac viec den gio",
            f"{task.get('task_id')} - {task.get('ten_cong_viec')}",
            {
                "loai_lich": task.get("type"),
                "gio": task.get("time"),
                "thu": task.get("weekday") or "-",
                "ngay_chay_mot_lan": task.get("once_date") or "-",
                "nhom": task.get("group") or "-",
                "huong_dan": "Vao module Quan ly cong viec va bam Hoan thanh de tat/an lich.",
            },
        )

    def test(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "ok": False,
                "message": "Chua cau hinh TELEGRAM_TOKEN/BOT_TOKEN hoac MY_TELEGRAM_ID.",
                "details": {"bot": self.settings.bot_username, "chat_id": self.chat_id},
            }
        try:
            with httpx.Client(timeout=15) as client:
                response = client.get(f"https://api.telegram.org/bot{self.token}/getMe")
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "message": "Token Telegram khong hop le hoac Bot API khong phan hoi.",
                    "details": {"status_code": response.status_code, "bot": self.settings.bot_username},
                }
            data = response.json()
            bot_username = data.get("result", {}).get("username") or self.settings.bot_username
            sent = self.send_message(
                "Kiem tra Telegram",
                "Bot da ket noi thanh cong va chi gui tin ve MY_TELEGRAM_ID da cau hinh.",
                {"chat_id": self.chat_id, "bot": bot_username},
            )
            return {
                "ok": bool(data.get("ok") and sent),
                "message": "Ket noi Telegram thanh cong." if sent else "Bot hop le nhung chua gui duoc tin den MY_TELEGRAM_ID. Hay bam Start trong bot.",
                "details": {"bot": bot_username, "chat_id": self.chat_id, "sent_to_owner": sent},
            }
        except httpx.TimeoutException:
            return {
                "ok": False,
                "message": "Telegram phan hoi qua lau.",
                "details": {"bot": self.settings.bot_username, "chat_id": self.chat_id},
            }
        except httpx.RequestError:
            return {
                "ok": False,
                "message": "Khong ket noi duoc Telegram Bot API.",
                "details": {"bot": self.settings.bot_username, "chat_id": self.chat_id},
            }
