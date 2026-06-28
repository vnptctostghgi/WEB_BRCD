import hmac
import logging
from typing import Any

import httpx

from app.settings import Settings


logger = logging.getLogger(__name__)


class ZaloBotClient:
    api_root = "https://bot-api.zaloplatforms.com"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.token = settings.zalo_bot_token.get_secret_value().strip().strip('"').strip("'")
        self.webhook_url = settings.zalo_webhook_url.strip()
        self.webhook_secret = settings.zalo_webhook_secret.get_secret_value().strip()
        self.auto_reply_enabled = settings.zalo_auto_reply_enabled

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    @property
    def webhook_ready(self) -> bool:
        return bool(self.token and self.webhook_url and self.webhook_secret)

    def api_url(self, method: str) -> str:
        safe_method = method.strip("/")
        return f"{self.api_root}/bot{self.token}/{safe_method}"

    def call_api(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "message": "Chua cau hinh ZALO_BOT_TOKEN.", "details": None}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(self.api_url(method), json=payload or {})
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "message": f"Zalo Bot API tra loi HTTP {response.status_code}.",
                    "details": {"status_code": response.status_code, "body": response.text[:300]},
                }
            data = response.json()
            if data.get("ok") is False:
                return {
                    "ok": False,
                    "message": "Zalo Bot API bao loi.",
                    "details": self._safe_details(data),
                }
            return data
        except httpx.TimeoutException:
            return {"ok": False, "message": "Zalo Bot API phan hoi qua lau.", "details": None}
        except (httpx.RequestError, ValueError):
            logger.exception("Zalo Bot API request failed")
            return {"ok": False, "message": "Khong ket noi duoc Zalo Bot API.", "details": None}

    def get_me(self) -> dict[str, Any]:
        return self.call_api("getMe")

    def get_webhook_info(self) -> dict[str, Any]:
        return self.call_api("getWebhookInfo")

    def configure_webhook(self) -> dict[str, Any]:
        if not self.webhook_ready:
            return {
                "ok": False,
                "message": "Chua cau hinh du ZALO_BOT_TOKEN, ZALO_WEBHOOK_URL va ZALO_WEBHOOK_SECRET.",
                "details": {
                    "has_token": bool(self.token),
                    "has_webhook_url": bool(self.webhook_url),
                    "has_webhook_secret": bool(self.webhook_secret),
                },
            }
        result = self.call_api("setWebhook", {"url": self.webhook_url, "secret_token": self.webhook_secret})
        if result.get("ok") is False:
            return result
        return {
            "ok": True,
            "message": "Da cai dat webhook Zalo Bot.",
            "details": {"webhook_url": result.get("result", {}).get("url") or self.webhook_url},
        }

    def send_message(self, chat_id: str, text: str, parse_mode: str | None = None) -> bool:
        if not self.enabled or not chat_id or not text:
            return False
        payload: dict[str, Any] = {"chat_id": str(chat_id), "text": text[:2000]}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        result = self.call_api("sendMessage", payload)
        if result.get("ok") is False:
            logger.warning("Zalo sendMessage failed: %s", result)
            return False
        return True

    def test(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "ok": False,
                "message": "Chua cau hinh ZALO_BOT_TOKEN.",
                "details": {"webhook_url": self.webhook_url or ""},
            }
        me = self.get_me()
        if me.get("ok") is False:
            return me
        webhook = self.get_webhook_info()
        bot = me.get("result", {}) if isinstance(me.get("result"), dict) else {}
        webhook_result = webhook.get("result", {}) if isinstance(webhook.get("result"), dict) else {}
        configured_url = str(webhook_result.get("url") or "")
        webhook_matches = bool(self.webhook_url and configured_url == self.webhook_url)
        message = "Ket noi Zalo Bot thanh cong."
        if self.webhook_url and not webhook_matches:
            message = "Token Zalo hop le, nhung webhook chua tro ve URL production hien tai."
        return {
            "ok": True,
            "message": message,
            "details": {
                "bot_id": bot.get("id"),
                "account_name": bot.get("account_name"),
                "account_type": bot.get("account_type"),
                "can_join_groups": bot.get("can_join_groups"),
                "webhook_url": configured_url or "",
                "expected_webhook_url": self.webhook_url or "",
                "webhook_matches": webhook_matches,
            },
        }

    def has_valid_webhook_secret(self, header_value: str | None) -> bool:
        if not self.webhook_secret:
            return False
        return hmac.compare_digest(str(header_value or ""), self.webhook_secret)

    def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = payload.get("result") if isinstance(payload, dict) else {}
        result = result if isinstance(result, dict) else {}
        event_name = str(result.get("event_name") or "")
        message = result.get("message") if isinstance(result.get("message"), dict) else {}
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = str(chat.get("id") or "")
        text = str(message.get("text") or "").strip()
        auto_replied = False

        if self.auto_reply_enabled and event_name == "message.text.received" and chat_id:
            auto_replied = self.send_message(chat_id, self.reply_text(text))

        return {
            "ok": True,
            "event_name": event_name,
            "chat_id": chat_id,
            "auto_replied": auto_replied,
        }

    @staticmethod
    def reply_text(text: str) -> str:
        normalized = text.strip().lower()
        if normalized in {"/start", "start", "/help", "help", "tro giup", "trợ giúp"}:
            return "Bot VNPT CTO da ket noi. Hay gui tin nhan de kiem tra kenh Zalo Bot."
        if normalized == "ping":
            return "pong"
        return "Bot VNPT CTO da nhan tin nhan cua ban."

    @staticmethod
    def _safe_details(data: dict[str, Any]) -> dict[str, Any]:
        safe = dict(data)
        safe.pop("token", None)
        return safe
