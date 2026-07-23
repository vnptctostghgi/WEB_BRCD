from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any


class InternalEmailRepository:
    def __init__(self, base_repository: Any) -> None:
        self.base = base_repository
        self.is_sqlite = hasattr(base_repository, "connect")

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

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

    def _upsert(self, table: str, payload: dict[str, Any], conflict: str) -> None:
        self.base._upsert(table, payload, conflict)

    @staticmethod
    def _decode_message(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["is_otp_candidate"] = bool(item.get("is_otp_candidate"))
        return item

    def get_message_by_uid(self, account_key: str, mailbox: str, uid: str) -> dict[str, Any] | None:
        if self.is_sqlite:
            row = self._sqlite_one(
                "SELECT * FROM internal_email_messages WHERE account_key=? AND mailbox=? AND uid=?",
                (account_key, mailbox, str(uid)),
            )
        else:
            rows = self._get(
                "internal_email_messages",
                {
                    "account_key": f"eq.{account_key}",
                    "mailbox": f"eq.{mailbox}",
                    "uid": f"eq.{uid}",
                    "limit": "1",
                },
            )
            row = rows[0] if rows else None
        return self._decode_message(row) if row else None

    def save_message(self, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        account_key = str(payload.get("account_key") or "internal_email")
        mailbox = str(payload.get("mailbox") or "INBOX")
        uid = str(payload.get("uid") or "")
        existing = self.get_message_by_uid(account_key, mailbox, uid) if uid else None
        created = existing is None
        now = self.now()
        row = {
            "account_key": account_key,
            "mailbox": mailbox,
            "uid": uid,
            "message_id": str(payload.get("message_id") or ""),
            "sender": str(payload.get("sender") or ""),
            "sender_email": str(payload.get("sender_email") or ""),
            "subject": str(payload.get("subject") or ""),
            "body_masked": str(payload.get("body_masked") or ""),
            "received_at": str(payload.get("received_at") or now),
            "synced_at": str(payload.get("synced_at") or now),
            "is_otp_candidate": bool(payload.get("is_otp_candidate")),
            "otp_code_masked": str(payload.get("otp_code_masked") or ""),
            "otp_service_code": str(payload.get("otp_service_code") or ""),
            "otp_request_id": str(payload.get("otp_request_id") or ""),
            "created_at": str(existing.get("created_at") if existing else payload.get("created_at") or now),
            "updated_at": now,
        }
        if self.is_sqlite:
            sqlite_row = {**row, "is_otp_candidate": int(bool(row["is_otp_candidate"]))}
            with self.base.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO internal_email_messages
                    (account_key, mailbox, uid, message_id, sender, sender_email, subject, body_masked,
                     received_at, synced_at, is_otp_candidate, otp_code_masked, otp_service_code,
                     otp_request_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_key, mailbox, uid) DO UPDATE SET
                      message_id=excluded.message_id,
                      sender=excluded.sender,
                      sender_email=excluded.sender_email,
                      subject=excluded.subject,
                      body_masked=excluded.body_masked,
                      received_at=excluded.received_at,
                      synced_at=excluded.synced_at,
                      is_otp_candidate=excluded.is_otp_candidate,
                      otp_code_masked=excluded.otp_code_masked,
                      otp_service_code=excluded.otp_service_code,
                      otp_request_id=excluded.otp_request_id,
                      updated_at=excluded.updated_at
                    """,
                    (
                        sqlite_row["account_key"],
                        sqlite_row["mailbox"],
                        sqlite_row["uid"],
                        sqlite_row["message_id"],
                        sqlite_row["sender"],
                        sqlite_row["sender_email"],
                        sqlite_row["subject"],
                        sqlite_row["body_masked"],
                        sqlite_row["received_at"],
                        sqlite_row["synced_at"],
                        sqlite_row["is_otp_candidate"],
                        sqlite_row["otp_code_masked"],
                        sqlite_row["otp_service_code"],
                        sqlite_row["otp_request_id"],
                        sqlite_row["created_at"],
                        sqlite_row["updated_at"],
                    ),
                )
            saved = self.get_message_by_uid(account_key, mailbox, uid) or row
            return saved, created
        try:
            if existing:
                payload_for_patch = dict(row)
                payload_for_patch.pop("created_at", None)
                self._patch(
                    "internal_email_messages",
                    {"account_key": f"eq.{account_key}", "mailbox": f"eq.{mailbox}", "uid": f"eq.{uid}"},
                    payload_for_patch,
                )
                saved = self.get_message_by_uid(account_key, mailbox, uid) or row
            else:
                saved = self._insert("internal_email_messages", row)
        except sqlite3.IntegrityError:
            saved = self.get_message_by_uid(account_key, mailbox, uid) or row
            created = False
        return self._decode_message(saved), created

    def mark_message_otp(self, message_id: str | int, otp_service_code: str, otp_code_masked: str, otp_request_id: str = "") -> None:
        now = self.now()
        payload = {
            "is_otp_candidate": True,
            "otp_service_code": otp_service_code,
            "otp_code_masked": otp_code_masked,
            "otp_request_id": otp_request_id,
            "updated_at": now,
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    """
                    UPDATE internal_email_messages
                    SET is_otp_candidate=1, otp_service_code=?, otp_code_masked=?, otp_request_id=?, updated_at=?
                    WHERE id=?
                    """,
                    (otp_service_code, otp_code_masked, otp_request_id, now, message_id),
                )
            return
        self._patch("internal_email_messages", {"id": f"eq.{message_id}"}, payload)

    def list_messages(self, limit: int = 20, otp_only: bool = False) -> list[dict[str, Any]]:
        safe_limit = min(max(int(limit or 20), 1), 100)
        if self.is_sqlite:
            where = "WHERE is_otp_candidate=1" if otp_only else ""
            rows = self._sqlite_rows(
                f"SELECT * FROM internal_email_messages {where} ORDER BY received_at DESC, id DESC LIMIT ?",
                (safe_limit,),
            )
        else:
            params = {"order": "received_at.desc,id.desc", "limit": str(safe_limit)}
            if otp_only:
                params["is_otp_candidate"] = "eq.true"
            rows = self._get("internal_email_messages", params)
        return [self._decode_message(row) for row in rows]
