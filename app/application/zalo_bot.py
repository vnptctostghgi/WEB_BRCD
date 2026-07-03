import hmac
import json
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

    def send_chat_action(self, chat_id: str, action: str = "typing") -> bool:
        if not self.enabled or not chat_id:
            return False
        result = self.call_api("sendChatAction", {"chat_id": str(chat_id), "action": action})
        if result.get("ok") is False:
            logger.warning("Zalo sendChatAction failed: %s", result)
            return False
        return True

    def send_photo(self, chat_id: str, photo_url: str, caption: str = "") -> bool:
        if not self.enabled or not chat_id or not photo_url:
            return False
        payload: dict[str, Any] = {"chat_id": str(chat_id), "photo": photo_url}
        if caption:
            payload["caption"] = caption[:2000]
        self.send_chat_action(chat_id, "upload_photo")
        result = self.call_api("sendPhoto", payload)
        if result.get("ok") is False:
            logger.warning("Zalo sendPhoto failed: %s", result)
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
        return hmac.compare_digest(str(header_value or "").strip(), self.webhook_secret)

    def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = self._as_dict(payload)
        result = self._as_dict(body.get("result"))
        raw_message = result.get("message") or body.get("message")
        message = self._as_dict(raw_message)
        if not message:
            message = self._find_nested_dict(result, {"chat", "from", "text", "message_id", "caption", "photo", "voice_url"})
        if not message:
            message = self._find_nested_dict(body, {"chat", "from", "text", "message_id", "caption", "photo", "voice_url"})

        event_name = self._first_string("event_name", "eventName", "event", sources=(result, body))
        sender = self._as_dict(message.get("from") or message.get("sender") or message.get("user"))
        chat = self._as_dict(message.get("chat") or result.get("chat") or body.get("chat"))
        chat_id = self._first_string("id", "chat_id", "chatId", "conversation_id", "conversationId", "group_id", "groupId", "user_id", sources=(chat, message, result, body))
        chat_type = self._first_string("chat_type", "chatType", "type", sources=(chat, message, result, body))
        text = self._message_text(raw_message, message, result, body)
        reply_text = ""
        auto_replied = False

        if self.auto_reply_enabled and event_name == "message.text.received" and chat_id:
            reply_text = self.reply_text(text)
            auto_replied = self.send_message(chat_id, reply_text)

        return {
            "ok": True,
            "event_name": event_name,
            "chat_id": chat_id,
            "chat_type": chat_type,
            "from_id": str(sender.get("id") or ""),
            "from_name": str(sender.get("display_name") or sender.get("name") or ""),
            "message_id": self._first_string("message_id", "messageId", "id", sources=(message, result, body)),
            "text": text,
            "reply_text": reply_text,
            "raw_keys": sorted(body.keys()),
            "result_keys": sorted(result.keys()),
            "message_keys": sorted(message.keys()),
            "raw_preview": self._payload_preview(body),
            "auto_replied": auto_replied,
        }

    @staticmethod
    def reply_text(text: str) -> str:
        normalized = text.strip().lower()
        if any(command in normalized for command in ("/start", "/help", "help", "tro giup", "trợ giúp")):
            return "Bot VNPT CTO da ket noi. Hay gui tin nhan de kiem tra kenh Zalo Bot."
        if "ping" in normalized:
            return "pong"
        return "Bot VNPT CTO da nhan tin nhan cua ban."

    @staticmethod
    def _safe_details(data: dict[str, Any]) -> dict[str, Any]:
        safe = dict(data)
        safe.pop("token", None)
        return safe

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @classmethod
    def _find_nested_dict(cls, value: Any, wanted_keys: set[str]) -> dict[str, Any]:
        if isinstance(value, str):
            value = cls._as_dict(value)
        if isinstance(value, dict):
            if wanted_keys.intersection(value.keys()):
                return value
            for child in value.values():
                found = cls._find_nested_dict(child, wanted_keys)
                if found:
                    return found
        if isinstance(value, list):
            for child in value:
                found = cls._find_nested_dict(child, wanted_keys)
                if found:
                    return found
        return {}

    @staticmethod
    def _first_string(*keys: str, sources: tuple[dict[str, Any], ...]) -> str:
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if value is not None and not isinstance(value, (dict, list)):
                    return str(value).strip()
        return ""

    @classmethod
    def _message_text(cls, raw_message: Any, *sources: dict[str, Any]) -> str:
        for key in ("text", "message_text", "content", "caption"):
            value = cls._first_string(key, sources=sources)
            if value:
                return value
        if isinstance(raw_message, str):
            parsed = cls._as_dict(raw_message)
            if not parsed:
                return raw_message.strip()
        return ""

    @classmethod
    def _payload_preview(cls, payload: dict[str, Any], limit: int = 1800) -> str:
        try:
            text = json.dumps(cls._sanitize_for_log(payload), ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            text = str(payload)
        return text if len(text) <= limit else f"{text[:limit]}..."

    @classmethod
    def _sanitize_for_log(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): cls._sanitize_for_log(child) for key, child in value.items() if str(key).lower() not in {"token", "secret", "secret_token"}}
        if isinstance(value, list):
            return [cls._sanitize_for_log(child) for child in value[:10]]
        if isinstance(value, str):
            return value if len(value) <= 500 else f"{value[:500]}..."
        return value
