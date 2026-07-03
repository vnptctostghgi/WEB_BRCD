from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlparse

from app.application.zalo_bot import ZaloBotClient
from app.settings import Settings


def public_base_url(settings: Settings) -> str:
    configured = str(getattr(settings, "app_public_url", "") or "").strip().rstrip("/")
    if configured:
        return configured
    webhook_url = str(getattr(settings, "zalo_webhook_url", "") or "").strip()
    if "/api/zalo/webhook" in webhook_url:
        return webhook_url.split("/api/zalo/webhook", 1)[0].rstrip("/")
    parsed = urlparse(webhook_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return ""


def capture_public_url(settings: Settings, capture: dict[str, Any] | None) -> str:
    if not capture:
        return ""
    base_url = public_base_url(settings)
    capture_id = str(capture.get("capture_id") or "").strip()
    token = str(capture.get("public_token") or "").strip()
    if not base_url or not capture_id or not token:
        return ""
    return f"{base_url}/api/zalo/auto-message-captures/{quote(capture_id)}?token={quote(token)}"


def latest_zalo_chat_id_from_logs(repository: Any) -> str:
    for row in repository.list_audit_logs(limit=500):
        if row.get("action") != "zalo_message_received":
            continue
        try:
            details = json.loads(row.get("details") or "{}")
        except json.JSONDecodeError:
            continue
        chat_id = str(details.get("chat_id") or "").strip()
        if chat_id:
            return chat_id
    return ""


def auto_message_caption(schedule: dict[str, Any]) -> str:
    caption = str(schedule.get("caption") or "").strip()
    if caption:
        return caption
    title = str(schedule.get("name") or "Anh chup tu dong").strip()
    page = str(schedule.get("page_label") or schedule.get("page_url") or "").strip()
    return f"{title}\n{page}" if page else title


def log_zalo_auto_message(repository: Any, schedule: dict[str, Any], chat_id: str, text: str, ok: bool, photo_url: str) -> None:
    details = {
        "direction": "out",
        "event_name": "auto_schedule",
        "chat_id": chat_id,
        "chat_type": schedule.get("target_type") or "",
        "sender_id": "",
        "sender_name": schedule.get("chat_name") or "",
        "message_id": "",
        "text": text[:1000],
        "ok": ok,
        "raw_preview": photo_url[:1800],
        "raw_keys": [],
        "result_keys": [],
        "message_keys": [],
    }
    repository.add_audit_log(
        "zalo_auto",
        "zalo_message_sent" if ok else "zalo_message_send_failed",
        json.dumps(details, ensure_ascii=False),
    )
    repository.add_audit_log(
        "zalo_auto",
        "zalo_auto_message_sent" if ok else "zalo_auto_message_failed",
        f"{schedule.get('schedule_id')}: {schedule.get('name')} -> {chat_id}",
    )


def resolve_zalo_auto_photo_url(repository: Any, settings: Settings, schedule: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    latest_capture = repository.get_latest_zalo_message_capture(str(schedule.get("schedule_id") or ""), include_image=False)
    capture_url = capture_public_url(settings, latest_capture)
    if capture_url:
        return capture_url, latest_capture
    photo_url = str(schedule.get("photo_url") or "").strip()
    return photo_url, latest_capture


def send_zalo_auto_message(repository: Any, settings: Settings, schedule: dict[str, Any]) -> dict[str, Any]:
    chat_id = str(schedule.get("chat_id") or "").strip() or latest_zalo_chat_id_from_logs(repository)
    if not chat_id:
        return {"ok": False, "message": "Chua co chat_id Zalo de gui lich tu dong.", "chat_id": "", "photo_url": ""}
    photo_url, latest_capture = resolve_zalo_auto_photo_url(repository, settings, schedule)
    if not photo_url:
        return {
            "ok": False,
            "message": "Chua co anh chup hoac URL anh HTTPS cho lich gui Zalo.",
            "chat_id": chat_id,
            "photo_url": "",
            "latest_capture": latest_capture,
        }
    parsed = urlparse(photo_url)
    if parsed.scheme != "https":
        return {"ok": False, "message": "URL anh gui Zalo phai dung HTTPS.", "chat_id": chat_id, "photo_url": photo_url}
    caption = auto_message_caption(schedule)
    sent = ZaloBotClient(settings).send_photo(chat_id, photo_url, caption)
    log_zalo_auto_message(repository, schedule, chat_id, caption, sent, photo_url)
    if not sent:
        return {"ok": False, "message": "Khong gui duoc anh qua Zalo.", "chat_id": chat_id, "photo_url": photo_url}
    return {"ok": True, "message": "Da gui anh qua Zalo.", "chat_id": chat_id, "photo_url": photo_url, "caption": caption}
