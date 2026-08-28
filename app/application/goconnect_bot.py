from __future__ import annotations

from typing import Any

import httpx


DEFAULT_ENDPOINT = "https://goconnect.vnpt.vn/api/v1/chatservice/bot/sendMessageByBot"


def normalize_goconnect_config(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        value = value[0] if value else {}
    if not isinstance(value, dict):
        raise ValueError("JSON chứng nhận Bot phải là một object hoặc mảng có một object.")
    rooms = []
    for room in value.get("rooms") or []:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("room_id") or room.get("roomId") or "").strip()
        if room_id:
            rooms.append({"room_id": room_id, "room_name": str(room.get("room_name") or room.get("roomName") or "").strip()})
    return {
        "endpoint": str(value.get("endpoint") or DEFAULT_ENDPOINT).strip(),
        "bot_id": str(value.get("bot_id") or value.get("botId") or "").strip(),
        "bot_code": str(value.get("bot_code") or value.get("botCode") or "").strip(),
        "bot_name": str(value.get("bot_name") or value.get("botName") or "").strip(),
        "tokenbot": str(value.get("tokenbot") or value.get("token") or "").strip(),
        "rooms": rooms,
    }


class GoConnectBotClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = normalize_goconnect_config(config)

    def validate(self) -> dict[str, Any]:
        missing = [key for key in ("bot_id", "tokenbot") if not self.config.get(key)]
        if not self.config.get("rooms"):
            missing.append("rooms")
        return {
            "ok": not missing,
            "message": "Cấu hình GoConnect Bot hợp lệ." if not missing else f"Thiếu cấu hình: {', '.join(missing)}.",
            "bot_name": self.config.get("bot_name", ""),
            "rooms": self.config.get("rooms", []),
        }

    def send_message(self, room_id: str, message: str) -> dict[str, Any]:
        response = httpx.post(
            self.config["endpoint"],
            headers={"x-gcn-token": self.config["tokenbot"], "Content-Type": "application/json"},
            json={"roomId": room_id, "message": message},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json() if "json" in response.headers.get("content-type", "") else {"response": response.text[:500]}
        return {"ok": True, "message": "Đã gửi tin qua GoConnect.", "room_id": room_id, "response": payload}
