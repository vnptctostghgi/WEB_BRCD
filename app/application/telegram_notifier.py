import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.settings import Settings


logger = logging.getLogger(__name__)
SENSITIVE_KEY_MARKERS = ("password", "token", "secret", "authorization", "cookie", "credential", "private_key", "api_key")
SENSITIVE_INLINE_PATTERN = re.compile(
    r"(?i)\b(password|token|secret|authorization|cookie|credential|private[_-]?key|api[_-]?key)\s*[:=]\s*[^\s,;&]+"
)
REDACTED = "[redacted]"


def sanitize_alert_text(value: Any, max_length: int = 800) -> str:
    text = str(value or "")
    text = SENSITIVE_INLINE_PATTERN.sub(lambda match: f"{match.group(1)}={REDACTED}", text)
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def sanitize_alert_details(details: dict[str, Any]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in details.items():
        normalized_key = str(key).lower()
        if any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
            sanitized[str(key)] = REDACTED
        else:
            sanitized[str(key)] = sanitize_alert_text(value, max_length=300)
    return sanitized


class TelegramNotifier:
    """Gui thong bao Telegram duy nhat den MY_TELEGRAM_ID cua quan tri vien."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        raw_token = settings.telegram_token.get_secret_value() or settings.bot_token.get_secret_value()
        self.token = raw_token.strip().strip('"').strip("'")
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
            sanitize_alert_text(message, max_length=1200),
        ]
        if details:
            details = sanitize_alert_details(details)
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
                logger.warning("Telegram send failed: %s %s", response.status_code, sanitize_alert_text(response.text, max_length=300))
                return False
            body = response.json()
            if not body.get("ok", True):
                logger.warning("Telegram API returned ok=false: %s", sanitize_alert_text(body, max_length=300))
                return False
            return True
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
