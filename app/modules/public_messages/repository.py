from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.modules.internal_email.repository import InternalEmailRepository
from app.modules.mobile_gateway import security
from app.modules.mobile_gateway.repository import MobileGatewayRepository
from app.settings import Settings


SOURCE_TYPES = {"email", "sms"}


class PublicMessagesRepository:
    def __init__(self, base_repository: Any, settings: Settings) -> None:
        self.base = base_repository
        self.settings = settings
        self.is_sqlite = hasattr(base_repository, "connect")

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    @staticmethod
    def _source_type(value: str) -> str:
        source_type = str(value or "").strip().lower()
        if source_type not in SOURCE_TYPES:
            raise ValueError("source_type must be email or sms")
        return source_type

    @staticmethod
    def _decode_rule(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["is_active"] = bool(item.get("is_active"))
        return item

    def _sqlite_rows(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.base.connect() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def _sqlite_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._sqlite_rows(query, params)
        return rows[0] if rows else None

    def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        return self.base._get(table, params)

    def _insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.base._insert(table, payload)

    def _patch(self, table: str, params: dict[str, str], payload: dict[str, Any]) -> None:
        self.base._patch(table, params, payload)

    def _delete(self, table: str, params: dict[str, str]) -> None:
        self.base._delete(table, params)

    def list_rules(self, source_type: str = "") -> list[dict[str, Any]]:
        safe_source = self._source_type(source_type) if source_type else ""
        if self.is_sqlite:
            if safe_source:
                rows = self._sqlite_rows(
                    "SELECT * FROM public_message_sender_rules WHERE source_type=? ORDER BY source_type, sender_pattern",
                    (safe_source,),
                )
            else:
                rows = self._sqlite_rows("SELECT * FROM public_message_sender_rules ORDER BY source_type, sender_pattern")
            return [self._decode_rule(row) for row in rows]
        params = {"order": "source_type.asc,sender_pattern.asc"}
        if safe_source:
            params["source_type"] = f"eq.{safe_source}"
        rows = self._get("public_message_sender_rules", params)
        return [self._decode_rule(row) for row in rows]

    def active_rules(self, source_type: str = "") -> list[dict[str, Any]]:
        return [
            rule
            for rule in self.list_rules(source_type)
            if rule.get("is_active") and str(rule.get("sender_pattern") or "").strip()
        ]

    def save_rule(
        self,
        *,
        source_type: str,
        sender_pattern: str,
        label: str = "",
        is_active: bool = True,
        actor: str = "",
    ) -> dict[str, Any]:
        safe_source = self._source_type(source_type)
        pattern = str(sender_pattern or "").strip()
        if not pattern:
            raise ValueError("sender_pattern is required")
        now = self.now()
        payload = {
            "source_type": safe_source,
            "sender_pattern": pattern,
            "label": str(label or "").strip(),
            "is_active": bool(is_active),
            "created_by": str(actor or ""),
            "created_at": now,
            "updated_at": now,
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO public_message_sender_rules
                    (source_type, sender_pattern, label, is_active, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_type, sender_pattern) DO UPDATE SET
                      label=excluded.label,
                      is_active=excluded.is_active,
                      updated_at=excluded.updated_at
                    """,
                    (
                        payload["source_type"],
                        payload["sender_pattern"],
                        payload["label"],
                        int(bool(payload["is_active"])),
                        payload["created_by"],
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
            row = self._sqlite_one(
                "SELECT * FROM public_message_sender_rules WHERE source_type=? AND sender_pattern=?",
                (safe_source, pattern),
            )
            return self._decode_rule(row or payload)

        source_rules = self._get("public_message_sender_rules", {"source_type": f"eq.{safe_source}"})
        existing = [rule for rule in source_rules if str(rule.get("sender_pattern") or "").lower() == pattern.lower()]
        if existing:
            update_payload = dict(payload)
            update_payload.pop("created_at", None)
            update_payload.pop("created_by", None)
            self._patch("public_message_sender_rules", {"id": f"eq.{existing[0]['id']}"}, update_payload)
            rows = self._get("public_message_sender_rules", {"id": f"eq.{existing[0]['id']}", "limit": "1"})
            return self._decode_rule(rows[0] if rows else {**existing[0], **update_payload})
        return self._decode_rule(self._insert("public_message_sender_rules", payload))

    def delete_rule(self, rule_id: str | int) -> None:
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute("DELETE FROM public_message_sender_rules WHERE id=?", (rule_id,))
            return
        self._delete("public_message_sender_rules", {"id": f"eq.{rule_id}"})

    @staticmethod
    def _matches_rule(rule: dict[str, Any], *values: str) -> bool:
        needle = str(rule.get("sender_pattern") or "").strip().lower()
        if not needle:
            return False
        return any(needle in str(value or "").lower() for value in values)

    @staticmethod
    def _sort_key(item: dict[str, Any]) -> datetime:
        value = str(item.get("received_at") or "")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)

    def _email_messages(self, limit: int, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages = InternalEmailRepository(self.base).list_messages(limit=limit, otp_only=False)
        items: list[dict[str, Any]] = []
        for message in messages:
            sender = str(message.get("sender") or "")
            sender_email = str(message.get("sender_email") or "")
            rule = next((candidate for candidate in rules if self._matches_rule(candidate, sender, sender_email)), None)
            if not rule:
                continue
            otp = str(message.get("otp_code") or message.get("otp_code_masked") or "")
            items.append(
                {
                    "id": f"email:{message.get('id')}",
                    "source_id": message.get("id"),
                    "rule_id": rule.get("id"),
                    "received_at": message.get("received_at") or message.get("synced_at") or "",
                    "sender": sender or sender_email,
                    "source_type": "email",
                    "type_label": "Mail n\u1ed9i b\u1ed9",
                    "title": message.get("subject") or "",
                    "otp": otp,
                    "content": message.get("body_masked") or "",
                }
            )
        return items

    def _sms_messages(self, limit: int, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages = MobileGatewayRepository(self.base, self.settings).latest_sms_messages(limit=limit)
        items: list[dict[str, Any]] = []
        for sms in messages:
            sender = str(sms.get("sender") or "")
            rule = next((candidate for candidate in rules if self._matches_rule(candidate, sender)), None)
            if not rule:
                continue
            body = str(sms.get("body") or sms.get("body_masked") or "")
            otp = security.extract_otp(body, security.OTP_DIGIT_PATTERN.pattern)
            items.append(
                {
                    "id": f"sms:{sms.get('id')}",
                    "source_id": sms.get("id"),
                    "rule_id": rule.get("id"),
                    "received_at": sms.get("received_at") or sms.get("synced_at") or "",
                    "sender": sender,
                    "source_type": "sms",
                    "type_label": "SMS",
                    "title": "",
                    "otp": otp,
                    "content": body,
                }
            )
        return items

    def list_public_messages(self, limit: int = 80) -> list[dict[str, Any]]:
        safe_limit = min(max(int(limit or 80), 1), 200)
        pool_limit = min(max(safe_limit * 5, 100), 500)
        email_rules = self.active_rules("email")
        sms_rules = self.active_rules("sms")
        items: list[dict[str, Any]] = []
        if email_rules:
            items.extend(self._email_messages(pool_limit, email_rules))
        if sms_rules:
            items.extend(self._sms_messages(pool_limit, sms_rules))
        items.sort(key=self._sort_key, reverse=True)
        return items[:safe_limit]
