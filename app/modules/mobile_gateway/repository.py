from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.mobile_gateway import security
from app.modules.mobile_gateway.schemas import (
    DevicePolicyPayload,
    HeartbeatPayload,
    NotificationIn,
    OtpConfigurationPayload,
    OtpFilterPayload,
    SmsMessageIn,
)
from app.settings import Settings


class MobileGatewayRepository:
    def __init__(self, base_repository: Any, settings: Settings) -> None:
        self.base = base_repository
        self.settings = settings
        self.is_sqlite = hasattr(base_repository, "connect")

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    @staticmethod
    def from_now(seconds: int) -> str:
        return (datetime.now(UTC) + timedelta(seconds=max(1, int(seconds)))).isoformat(timespec="seconds")

    @staticmethod
    def time_text(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, (int, float)):
            number = float(value)
            if number > 10_000_000_000:
                number = number / 1000
            return datetime.fromtimestamp(number, tz=UTC).isoformat(timespec="seconds")
        raw = str(value).strip()
        if raw.isdigit():
            number = int(raw)
            if number > 10_000_000_000:
                number = number / 1000
            return datetime.fromtimestamp(number, tz=UTC).isoformat(timespec="seconds")
        return raw

    @staticmethod
    def _json_loads(value: Any, fallback: Any) -> Any:
        if value in (None, ""):
            return fallback
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except (TypeError, ValueError):
            return fallback

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

    def _upsert(self, table: str, payload: dict[str, Any], conflict: str) -> None:
        self.base._upsert(table, payload, conflict)

    def ensure_defaults(self) -> None:
        if self.is_sqlite:
            return
        now = self.now()
        try:
            self._upsert(
                "otp_configurations",
                {
                    "service_code": "onebss",
                    "service_name": "OneBSS",
                    "enabled": True,
                    "source_type": "sms",
                    "sender_pattern": "VNPT",
                    "sender_match_type": "contains",
                    "otp_regex": r"(?<!\d)(\d{4,8})(?!\d)",
                    "otp_keyword": "",
                    "otp_length_min": 4,
                    "otp_length_max": 8,
                    "wait_timeout_seconds": 120,
                    "validity_seconds": 180,
                    "device_id": "",
                    "auto_fill_enabled": True,
                    "manual_fallback_enabled": True,
                    "priority": 10,
                    "created_at": now,
                    "updated_at": now,
                },
                "service_code",
            )
        except RuntimeError:
            pass
        try:
            existing_filter = next(
                (item for item in self.list_otp_filters(service_code="onebss") if item.get("filter_id") == "onebss"),
                None,
            )
            legacy_filter = (
                existing_filter
                and str(existing_filter.get("sender_pattern") or "").strip() == "293"
                and str(existing_filter.get("start_prefix") or "").strip() == "1364"
            )
            if not existing_filter or legacy_filter:
                self._upsert(
                    "otp_filter_configurations",
                    {
                        "filter_id": "onebss",
                        "rule_name": "OneBSS mac dinh",
                        "service_code": "onebss",
                        "sender_pattern": "VNPT",
                        "sender_match_type": "contains",
                        "otp_length": 6,
                        "start_prefix": "",
                        "validity_seconds": 60,
                        "enabled": True,
                        "device_id": "",
                        "sim_slot": None,
                        "priority": 10,
                        "created_at": now,
                        "updated_at": now,
                    },
                    "filter_id",
                )
        except RuntimeError:
            pass

    def create_pairing_code(self, code_hash: str, created_by: str, ttl_seconds: int, policy_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        now = self.now()
        policy = policy_payload or {}
        row = {
            "code_hash": code_hash,
            "created_by": created_by,
            "created_at": now,
            "expires_at": self.from_now(ttl_seconds),
            "used_at": None,
            "used_by_device_id": None,
            "policy_payload": policy if not self.is_sqlite else json.dumps(policy, ensure_ascii=False),
            "status": "active",
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO mobile_pairing_codes
                    (code_hash, created_by, created_at, expires_at, used_at, used_by_device_id, policy_payload, status)
                    VALUES (?, ?, ?, ?, NULL, NULL, ?, 'active')
                    """,
                    (row["code_hash"], row["created_by"], row["created_at"], row["expires_at"], row["policy_payload"]),
                )
                row["id"] = int(cursor.lastrowid)
            return row
        return self._insert("mobile_pairing_codes", row)

    def list_pairing_codes(self, limit: int = 20) -> list[dict[str, Any]]:
        self.expire_pairing_codes()
        if self.is_sqlite:
            return self._sqlite_rows(
                "SELECT id, created_by, created_at, expires_at, used_at, used_by_device_id, policy_payload, status FROM mobile_pairing_codes ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        return self._get(
            "mobile_pairing_codes",
            {"select": "id,created_by,created_at,expires_at,used_at,used_by_device_id,policy_payload,status", "order": "id.desc", "limit": str(limit)},
        )

    def get_pairing_code_by_hash(self, code_hash: str) -> dict[str, Any] | None:
        if self.is_sqlite:
            return self._sqlite_one("SELECT * FROM mobile_pairing_codes WHERE code_hash=?", (code_hash,))
        rows = self._get("mobile_pairing_codes", {"code_hash": f"eq.{code_hash}", "limit": "1"})
        return rows[0] if rows else None

    def mark_pairing_used(self, pairing_id: int, device_id: str) -> None:
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "UPDATE mobile_pairing_codes SET status='used', used_at=?, used_by_device_id=? WHERE id=? AND status='active'",
                    (now, device_id, pairing_id),
                )
            return
        self._patch("mobile_pairing_codes", {"id": f"eq.{pairing_id}", "status": "eq.active"}, {"status": "used", "used_at": now, "used_by_device_id": device_id})

    def expire_pairing_codes(self) -> None:
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute("UPDATE mobile_pairing_codes SET status='expired' WHERE status='active' AND expires_at<?", (now,))
            return
        self._patch("mobile_pairing_codes", {"status": "eq.active", "expires_at": f"lt.{now}"}, {"status": "expired"})

    def create_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = self.now()
        row = {
            "device_id": payload["device_id"],
            "name": payload.get("name") or payload.get("device_name") or payload["device_id"],
            "platform": payload.get("platform") or "android",
            "manufacturer": payload.get("manufacturer") or "",
            "model": payload.get("model") or "",
            "android_version": payload.get("android_version") or "",
            "app_version": payload.get("app_version") or "",
            "encrypted_device_secret": payload["encrypted_device_secret"],
            "is_active": True,
            "paired_at": now,
            "last_seen_at": now,
            "last_ip": payload.get("last_ip") or "",
            "revoked_at": None,
            "created_by": payload.get("created_by") or "",
            "created_at": now,
            "updated_at": now,
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO mobile_devices
                    (device_id, name, platform, manufacturer, model, android_version, app_version,
                     encrypted_device_secret, is_active, paired_at, last_seen_at, last_ip, revoked_at, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        row["device_id"], row["name"], row["platform"], row["manufacturer"], row["model"],
                        row["android_version"], row["app_version"], row["encrypted_device_secret"], row["paired_at"],
                        row["last_seen_at"], row["last_ip"], row["created_by"], row["created_at"], row["updated_at"],
                    ),
                )
                row["id"] = int(cursor.lastrowid)
            return row
        return self._insert("mobile_devices", row)

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        row = self.get_device_record(device_id)
        return self.decode_device(row) if row else None

    def get_device_record(self, device_id: str) -> dict[str, Any] | None:
        if self.is_sqlite:
            row = self._sqlite_one("SELECT * FROM mobile_devices WHERE device_id=?", (device_id,))
        else:
            rows = self._get("mobile_devices", {"device_id": f"eq.{device_id}", "limit": "1"})
            row = rows[0] if rows else None
        return row

    def list_devices(self) -> list[dict[str, Any]]:
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM mobile_devices ORDER BY COALESCE(last_seen_at, created_at) DESC")
        else:
            rows = self._get("mobile_devices", {"order": "last_seen_at.desc.nullslast,created_at.desc"})
        return [self.decode_device(row) for row in rows]

    def decode_device(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["is_active"] = bool(item.get("is_active"))
        item.pop("encrypted_device_secret", None)
        return item

    def device_secret(self, device: dict[str, Any]) -> str:
        raw = device.get("encrypted_device_secret") or ""
        return security.decrypt_text(self.settings, raw, "mobile")

    def update_device(self, device_id: str, payload: dict[str, Any]) -> None:
        payload = {**payload, "updated_at": self.now()}
        if self.is_sqlite:
            allowed = {"name", "is_active", "revoked_at", "last_seen_at", "last_ip", "app_version", "android_version", "manufacturer", "model"}
            fields = [key for key in payload if key in allowed]
            if not fields:
                return
            values = [int(payload[key]) if key == "is_active" else payload[key] for key in fields]
            with self.base.connect() as connection:
                connection.execute(
                    f"UPDATE mobile_devices SET {', '.join(f'{field}=?' for field in fields)}, updated_at=? WHERE device_id=?",
                    (*values, payload["updated_at"], device_id),
                )
            return
        self._patch("mobile_devices", {"device_id": f"eq.{device_id}"}, payload)

    def delete_device(self, device_id: str) -> None:
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute("DELETE FROM mobile_device_nonces WHERE device_id=?", (device_id,))
                connection.execute("DELETE FROM mobile_device_policies WHERE device_id=?", (device_id,))
                connection.execute("DELETE FROM mobile_devices WHERE device_id=?", (device_id,))
            return
        self._delete("mobile_device_nonces", {"device_id": f"eq.{device_id}"})
        self._delete("mobile_device_policies", {"device_id": f"eq.{device_id}"})
        self._delete("mobile_devices", {"device_id": f"eq.{device_id}"})

    def cleanup_nonces(self) -> None:
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute("DELETE FROM mobile_device_nonces WHERE expires_at < ?", (now,))
            return
        self._delete("mobile_device_nonces", {"expires_at": f"lt.{now}"})

    def nonce_exists(self, device_id: str, nonce: str) -> bool:
        if self.is_sqlite:
            return bool(self._sqlite_one("SELECT 1 FROM mobile_device_nonces WHERE device_id=? AND nonce=?", (device_id, nonce)))
        return bool(self._get("mobile_device_nonces", {"device_id": f"eq.{device_id}", "nonce": f"eq.{nonce}", "limit": "1"}))

    def save_nonce(self, device_id: str, nonce: str, expires_at: str) -> None:
        row = {"device_id": device_id, "nonce": nonce, "created_at": self.now(), "expires_at": expires_at}
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "INSERT INTO mobile_device_nonces (device_id, nonce, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (row["device_id"], row["nonce"], row["created_at"], row["expires_at"]),
                )
            return
        self._insert("mobile_device_nonces", row)

    def default_policy(self, device_id: str, updated_by: str = "system") -> dict[str, Any]:
        now = self.now()
        return {
            "device_id": device_id,
            "sms_enabled": True,
            "notifications_enabled": False,
            "clipboard_enabled": False,
            "camera_enabled": False,
            "diagnostics_enabled": True,
            "notification_allowlist": [],
            "heartbeat_interval_minutes": 15,
            "sync_interval_minutes": 15,
            "batch_size": 50,
            "local_retention_days": 14,
            "minimum_app_version": "1.3.0",
            "force_update": False,
            "updated_by": updated_by,
            "updated_at": now,
        }

    def save_policy(self, device_id: str, payload: DevicePolicyPayload | dict[str, Any], updated_by: str) -> dict[str, Any]:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        row = {**self.default_policy(device_id, updated_by), **data, "device_id": device_id, "updated_by": updated_by, "updated_at": self.now()}
        if self.is_sqlite:
            sqlite_row = {**row, "notification_allowlist": json.dumps(row["notification_allowlist"], ensure_ascii=False)}
            bool_fields = ["sms_enabled", "notifications_enabled", "clipboard_enabled", "camera_enabled", "diagnostics_enabled", "force_update"]
            for field in bool_fields:
                sqlite_row[field] = int(bool(sqlite_row[field]))
            with self.base.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO mobile_device_policies
                    (device_id, sms_enabled, notifications_enabled, clipboard_enabled, camera_enabled, diagnostics_enabled,
                     notification_allowlist, heartbeat_interval_minutes, sync_interval_minutes, batch_size,
                     local_retention_days, minimum_app_version, force_update, updated_by, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                      sms_enabled=excluded.sms_enabled,
                      notifications_enabled=excluded.notifications_enabled,
                      clipboard_enabled=excluded.clipboard_enabled,
                      camera_enabled=excluded.camera_enabled,
                      diagnostics_enabled=excluded.diagnostics_enabled,
                      notification_allowlist=excluded.notification_allowlist,
                      heartbeat_interval_minutes=excluded.heartbeat_interval_minutes,
                      sync_interval_minutes=excluded.sync_interval_minutes,
                      batch_size=excluded.batch_size,
                      local_retention_days=excluded.local_retention_days,
                      minimum_app_version=excluded.minimum_app_version,
                      force_update=excluded.force_update,
                      updated_by=excluded.updated_by,
                      updated_at=excluded.updated_at
                    """,
                    (
                        sqlite_row["device_id"], sqlite_row["sms_enabled"], sqlite_row["notifications_enabled"],
                        sqlite_row["clipboard_enabled"], sqlite_row["camera_enabled"], sqlite_row["diagnostics_enabled"], sqlite_row["notification_allowlist"],
                        sqlite_row["heartbeat_interval_minutes"], sqlite_row["sync_interval_minutes"], sqlite_row["batch_size"],
                        sqlite_row["local_retention_days"], sqlite_row["minimum_app_version"], sqlite_row["force_update"],
                        sqlite_row["updated_by"], sqlite_row["updated_at"],
                    ),
                )
            return self.get_policy(device_id)
        self._upsert("mobile_device_policies", row, "device_id")
        return self.get_policy(device_id)

    def get_policy(self, device_id: str) -> dict[str, Any]:
        if self.is_sqlite:
            row = self._sqlite_one("SELECT * FROM mobile_device_policies WHERE device_id=?", (device_id,))
        else:
            rows = self._get("mobile_device_policies", {"device_id": f"eq.{device_id}", "limit": "1"})
            row = rows[0] if rows else None
        if not row:
            return self.save_policy(device_id, self.default_policy(device_id), "system")
        return self.decode_policy(row)

    def decode_policy(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["notification_allowlist"] = self._json_loads(item.get("notification_allowlist"), [])
        for field in ["sms_enabled", "notifications_enabled", "clipboard_enabled", "camera_enabled", "diagnostics_enabled", "force_update"]:
            item[field] = bool(item.get(field))
        return item

    def save_heartbeat(self, device_id: str, payload: HeartbeatPayload, ip_address: str) -> dict[str, Any]:
        now = self.now()
        row = {
            **payload.model_dump(),
            "device_id": device_id,
            "created_at": now,
        }
        row["last_sms_received_at"] = self.time_text(row.get("last_sms_received_at")) or None
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO mobile_device_heartbeats
                    (device_id, app_version, android_version, manufacturer, model, battery_percent, charging,
                     network_type, pending_sms, pending_notifications, sms_permission, notification_access,
                     battery_optimization_ignored, last_sms_received_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_id, row["app_version"], row["android_version"], row["manufacturer"], row["model"],
                        row["battery_percent"], int(row["charging"]), row["network_type"], row["pending_sms"],
                        row["pending_notifications"], int(row["sms_permission"]), int(row["notification_access"]),
                        int(row["battery_optimization_ignored"]), row["last_sms_received_at"], now,
                    ),
                )
        else:
            self._insert("mobile_device_heartbeats", row)
        self.update_device(device_id, {
            "last_seen_at": now,
            "last_ip": ip_address,
            "app_version": payload.app_version,
            "android_version": payload.android_version,
            "manufacturer": payload.manufacturer,
            "model": payload.model,
        })
        return row

    def latest_heartbeats(self) -> dict[str, dict[str, Any]]:
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM mobile_device_heartbeats ORDER BY created_at DESC LIMIT 500")
        else:
            rows = self._get("mobile_device_heartbeats", {"order": "created_at.desc", "limit": "500"})
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            latest.setdefault(str(row.get("device_id")), row)
        return latest

    def save_sms_messages(self, device_id: str, messages: list[SmsMessageIn]) -> tuple[list[dict[str, Any]], int]:
        inserted: list[dict[str, Any]] = []
        skipped = 0
        now = self.now()
        for message in messages:
            body = message.body or ""
            row = {
                "device_id": device_id,
                "external_id": message.external_id,
                "sender": message.sender,
                "normalized_sender": security.normalize_sender(message.sender),
                "body_encrypted": security.encrypt_text(self.settings, body, "otp"),
                "body_masked": body,
                "received_at": self.time_text(message.received_at),
                "subscription_id": message.subscription_id or "",
                "sim_slot": message.sim_slot,
                "synced_at": now,
                "is_otp_candidate": bool(security.extract_otp(body, r"(?<!\d)(\d{4,8})(?!\d)")),
                "used_for_otp": False,
                "otp_request_id": None,
                "created_at": now,
            }
            try:
                if self.is_sqlite:
                    with self.base.connect() as connection:
                        cursor = connection.execute(
                            """
                            INSERT INTO mobile_sms_messages
                            (device_id, external_id, sender, normalized_sender, body_encrypted, body_masked,
                             received_at, subscription_id, sim_slot, synced_at, is_otp_candidate, used_for_otp,
                             otp_request_id, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                            """,
                            (
                                row["device_id"], row["external_id"], row["sender"], row["normalized_sender"],
                                row["body_encrypted"], row["body_masked"], row["received_at"], row["subscription_id"],
                                row["sim_slot"], row["synced_at"], int(row["is_otp_candidate"]), row["created_at"],
                            ),
                        )
                        row["id"] = int(cursor.lastrowid)
                else:
                    row = self._insert("mobile_sms_messages", row)
                inserted.append(self.decode_sms(row, include_body=True))
            except sqlite3.IntegrityError:
                skipped += 1
        return inserted, skipped

    def decode_sms(self, row: dict[str, Any], include_body: bool = False) -> dict[str, Any]:
        item = dict(row)
        item["is_otp_candidate"] = bool(item.get("is_otp_candidate"))
        item["used_for_otp"] = bool(item.get("used_for_otp"))
        decrypted_body = security.decrypt_text(self.settings, item.get("body_encrypted") or "", "otp") if include_body else ""
        item["body"] = decrypted_body or item.get("body_masked") or ""
        item.pop("body_encrypted", None)
        return item

    def list_sms(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        device_id: str = "",
        sender: str = "",
        query: str = "",
        date_from: str = "",
        date_to: str = "",
        sim_slot: str = "",
        otp_only: bool = False,
    ) -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 50)), 200)
        offset = (page - 1) * page_size
        if self.is_sqlite:
            clauses: list[str] = []
            params: list[Any] = []
            if device_id:
                clauses.append("device_id=?")
                params.append(device_id)
            if sender:
                clauses.append("sender LIKE ?")
                params.append(f"%{sender}%")
            if query:
                clauses.append("body_masked LIKE ?")
                params.append(f"%{query}%")
            if date_from:
                clauses.append("received_at>=?")
                params.append(date_from)
            if date_to:
                clauses.append("received_at<=?")
                params.append(date_to)
            if sim_slot not in ("", None):
                clauses.append("sim_slot=?")
                params.append(int(sim_slot))
            if otp_only:
                clauses.append("is_otp_candidate=1")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = self._sqlite_rows(
                f"SELECT * FROM mobile_sms_messages {where} ORDER BY received_at DESC, id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            )
        else:
            params = {"order": "received_at.desc,id.desc", "limit": str(page_size), "offset": str(offset)}
            if device_id:
                params["device_id"] = f"eq.{device_id}"
            if sender:
                params["sender"] = f"ilike.*{sender}*"
            if query:
                params["body_masked"] = f"ilike.*{query}*"
            if date_from and date_to:
                params["and"] = f"(received_at.gte.{date_from},received_at.lte.{date_to})"
            elif date_from:
                params["received_at"] = f"gte.{date_from}"
            elif date_to:
                params["received_at"] = f"lte.{date_to}"
            if sim_slot not in ("", None):
                params["sim_slot"] = f"eq.{sim_slot}"
            if otp_only:
                params["is_otp_candidate"] = "eq.true"
            rows = self._get("mobile_sms_messages", params)
        return {"items": [self.decode_sms(row, include_body=True) for row in rows], "page": page, "page_size": page_size, "has_more": len(rows) == page_size}

    def get_sms(self, sms_id: str | int) -> dict[str, Any] | None:
        if self.is_sqlite:
            row = self._sqlite_one("SELECT * FROM mobile_sms_messages WHERE id=?", (sms_id,))
        else:
            rows = self._get("mobile_sms_messages", {"id": f"eq.{sms_id}", "limit": "1"})
            row = rows[0] if rows else None
        return self.decode_sms(row, include_body=True) if row else None

    def latest_sms_messages(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = min(max(1, int(limit or 200)), 500)
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM mobile_sms_messages ORDER BY received_at DESC, id DESC LIMIT ?", (limit,))
        else:
            rows = self._get("mobile_sms_messages", {"order": "received_at.desc,id.desc", "limit": str(limit)})
        return [self.decode_sms(row, include_body=True) for row in rows]

    def mark_sms_matched(self, sms_id: str | int, request_id: str, used: bool = False) -> None:
        payload = {"otp_request_id": request_id}
        if used:
            payload["used_for_otp"] = True
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "UPDATE mobile_sms_messages SET otp_request_id=?, used_for_otp=? WHERE id=?",
                    (request_id, int(used), sms_id),
                )
            return
        self._patch("mobile_sms_messages", {"id": f"eq.{sms_id}"}, payload)

    def save_notifications(self, device_id: str, notifications: list[NotificationIn]) -> tuple[list[dict[str, Any]], int]:
        inserted: list[dict[str, Any]] = []
        skipped = 0
        now = self.now()
        for item in notifications:
            text = item.text or ""
            row = {
                "device_id": device_id,
                "external_id": item.external_id,
                "package_name": item.package_name,
                "app_name": item.app_name or "",
                "title": item.title or "",
                "text_encrypted": security.encrypt_text(self.settings, text, "otp"),
                "text_masked": security.mask_otp_text(text),
                "posted_at": self.time_text(item.posted_at),
                "used_for_otp": False,
                "otp_request_id": None,
                "created_at": now,
            }
            try:
                if self.is_sqlite:
                    with self.base.connect() as connection:
                        cursor = connection.execute(
                            """
                            INSERT INTO mobile_notifications
                            (device_id, external_id, package_name, app_name, title, text_encrypted, text_masked,
                             posted_at, used_for_otp, otp_request_id, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                            """,
                            (
                                row["device_id"], row["external_id"], row["package_name"], row["app_name"], row["title"],
                                row["text_encrypted"], row["text_masked"], row["posted_at"], row["created_at"],
                            ),
                        )
                        row["id"] = int(cursor.lastrowid)
                else:
                    row = self._insert("mobile_notifications", row)
                inserted.append(self.decode_notification(row, include_text=True))
            except sqlite3.IntegrityError:
                skipped += 1
        return inserted, skipped

    def decode_notification(self, row: dict[str, Any], include_text: bool = False) -> dict[str, Any]:
        item = dict(row)
        item["used_for_otp"] = bool(item.get("used_for_otp"))
        item["text"] = security.decrypt_text(self.settings, item.get("text_encrypted") or "", "otp") if include_text else item.get("text_masked") or ""
        item.pop("text_encrypted", None)
        return item

    def list_notifications(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        device_id: str = "",
        package_name: str = "",
        query: str = "",
    ) -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 50)), 200)
        offset = (page - 1) * page_size
        if self.is_sqlite:
            clauses: list[str] = []
            params: list[Any] = []
            if device_id:
                clauses.append("device_id=?")
                params.append(device_id)
            if package_name:
                clauses.append("(package_name LIKE ? OR app_name LIKE ?)")
                params.extend([f"%{package_name}%", f"%{package_name}%"])
            if query:
                clauses.append("(title LIKE ? OR text_masked LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = self._sqlite_rows(
                f"SELECT * FROM mobile_notifications {where} ORDER BY posted_at DESC, id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            )
        else:
            params = {"order": "posted_at.desc,id.desc", "limit": str(page_size), "offset": str(offset)}
            if device_id:
                params["device_id"] = f"eq.{device_id}"
            if package_name:
                params["package_name"] = f"ilike.*{package_name}*"
            if query:
                params["text_masked"] = f"ilike.*{query}*"
            rows = self._get("mobile_notifications", params)
        return {"items": [self.decode_notification(row, include_text=True) for row in rows], "page": page, "page_size": page_size, "has_more": len(rows) == page_size}

    def mark_notification_matched(self, notification_id: str | int, request_id: str, used: bool = False) -> None:
        payload = {"otp_request_id": request_id}
        if used:
            payload["used_for_otp"] = True
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "UPDATE mobile_notifications SET otp_request_id=?, used_for_otp=? WHERE id=?",
                    (request_id, int(used), notification_id),
                )
            return
        self._patch("mobile_notifications", {"id": f"eq.{notification_id}"}, payload)

    def create_command(self, device_id: str, command_type: str, payload: dict[str, Any], created_by: str, ttl_seconds: int) -> dict[str, Any]:
        row = {
            "command_id": f"CMD{uuid.uuid4().hex[:18].upper()}",
            "device_id": device_id,
            "command_type": command_type,
            "payload": payload if not self.is_sqlite else json.dumps(payload, ensure_ascii=False),
            "status": "pending",
            "created_by": created_by,
            "created_at": self.now(),
            "expires_at": self.from_now(ttl_seconds),
            "delivered_at": None,
            "acknowledged_at": None,
            "completed_at": None,
            "sanitized_error": "",
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO mobile_commands
                    (command_id, device_id, command_type, payload, status, created_by, created_at, expires_at,
                     delivered_at, acknowledged_at, completed_at, sanitized_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, '')
                    """,
                    (row["command_id"], device_id, command_type, row["payload"], row["status"], created_by, row["created_at"], row["expires_at"]),
                )
        else:
            self._insert("mobile_commands", row)
        return self.decode_command(row)

    def decode_command(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["payload"] = self._json_loads(item.get("payload"), {})
        return item

    def list_commands(self, device_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        if self.is_sqlite:
            if device_id:
                rows = self._sqlite_rows("SELECT * FROM mobile_commands WHERE device_id=? ORDER BY created_at DESC LIMIT ?", (device_id, limit))
            else:
                rows = self._sqlite_rows("SELECT * FROM mobile_commands ORDER BY created_at DESC LIMIT ?", (limit,))
        else:
            params = {"order": "created_at.desc", "limit": str(limit)}
            if device_id:
                params["device_id"] = f"eq.{device_id}"
            rows = self._get("mobile_commands", params)
        return [self.decode_command(row) for row in rows]

    def deliver_pending_commands(self, device_id: str) -> list[dict[str, Any]]:
        now = self.now()
        if self.is_sqlite:
            rows = self._sqlite_rows(
                "SELECT * FROM mobile_commands WHERE device_id=? AND status='pending' AND expires_at>=? ORDER BY created_at LIMIT 20",
                (device_id, now),
            )
            ids = [row["command_id"] for row in rows]
            if ids:
                with self.base.connect() as connection:
                    connection.executemany("UPDATE mobile_commands SET status='delivered', delivered_at=? WHERE command_id=?", [(now, command_id) for command_id in ids])
        else:
            rows = self._get("mobile_commands", {"device_id": f"eq.{device_id}", "status": "eq.pending", "expires_at": f"gte.{now}", "order": "created_at.asc", "limit": "20"})
            for row in rows:
                self._patch("mobile_commands", {"command_id": f"eq.{row['command_id']}"}, {"status": "delivered", "delivered_at": now})
        return [self.decode_command(row) for row in rows]

    def finish_command(self, command_id: str, device_id: str, status_value: str, result: dict[str, Any], sanitized_error: str) -> None:
        now = self.now()
        payload = {
            "status": status_value,
            "sanitized_error": sanitized_error[:500],
        }
        if status_value == "acknowledged":
            payload["acknowledged_at"] = now
        else:
            payload["completed_at"] = now
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "UPDATE mobile_commands SET status=?, sanitized_error=?, acknowledged_at=COALESCE(acknowledged_at, ?), completed_at=? WHERE command_id=? AND device_id=?",
                    (status_value, sanitized_error[:500], now, now if status_value != "acknowledged" else None, command_id, device_id),
                )
                connection.execute(
                    "INSERT INTO mobile_command_logs (command_id, device_id, status, payload, sanitized_error, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (command_id, device_id, status_value, json.dumps(result, ensure_ascii=False), sanitized_error[:500], now),
                )
            return
        self._patch("mobile_commands", {"command_id": f"eq.{command_id}", "device_id": f"eq.{device_id}"}, payload)
        self._insert("mobile_command_logs", {"command_id": command_id, "device_id": device_id, "status": status_value, "payload": result, "sanitized_error": sanitized_error[:500], "created_at": now})

    def save_diagnostics(self, device_id: str, payload: dict[str, Any]) -> None:
        row = {
            "device_id": device_id,
            "app_version": str(payload.get("app_version") or ""),
            "android_version": str(payload.get("android_version") or ""),
            "manufacturer": str(payload.get("manufacturer") or ""),
            "model": str(payload.get("model") or ""),
            "payload": payload.get("payload") if not self.is_sqlite else json.dumps(payload.get("payload") or {}, ensure_ascii=False),
            "sanitized_error": str(payload.get("sanitized_error") or "")[:1000],
            "created_at": self.now(),
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "INSERT INTO mobile_diagnostics (device_id, app_version, android_version, manufacturer, model, payload, sanitized_error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (row["device_id"], row["app_version"], row["android_version"], row["manufacturer"], row["model"], row["payload"], row["sanitized_error"], row["created_at"]),
                )
            return
        self._insert("mobile_diagnostics", row)

    def list_diagnostics(self, limit: int = 100) -> list[dict[str, Any]]:
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM mobile_diagnostics ORDER BY created_at DESC LIMIT ?", (limit,))
        else:
            rows = self._get("mobile_diagnostics", {"order": "created_at.desc", "limit": str(limit)})
        for row in rows:
            row["payload"] = self._json_loads(row.get("payload"), {})
        return rows

    def save_media(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = self.now()
        row = {
            "device_id": str(payload.get("device_id") or ""),
            "command_id": str(payload.get("command_id") or ""),
            "media_type": str(payload.get("media_type") or ""),
            "file_name": str(payload.get("file_name") or ""),
            "mime_type": str(payload.get("mime_type") or ""),
            "size_bytes": int(payload.get("size_bytes") or 0),
            "captured_at": payload.get("captured_at") or None,
            "uploaded_at": payload.get("uploaded_at") or now,
            "drive_file_id": str(payload.get("drive_file_id") or ""),
            "drive_url": str(payload.get("drive_url") or ""),
            "status": str(payload.get("status") or "pending"),
            "error_message": str(payload.get("error_message") or "")[:1000],
            "created_at": now,
            "updated_at": now,
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO mobile_media
                    (device_id, command_id, media_type, file_name, mime_type, size_bytes, captured_at,
                     uploaded_at, drive_file_id, drive_url, status, error_message, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["device_id"], row["command_id"], row["media_type"], row["file_name"], row["mime_type"],
                        row["size_bytes"], row["captured_at"], row["uploaded_at"], row["drive_file_id"], row["drive_url"],
                        row["status"], row["error_message"], row["created_at"], row["updated_at"],
                    ),
                )
                row["id"] = int(cursor.lastrowid)
            return row
        return self._insert("mobile_media", row)

    def list_media(self, *, page: int = 1, page_size: int = 50, device_id: str = "", media_type: str = "") -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 50)), 100)
        offset = (page - 1) * page_size
        if self.is_sqlite:
            clauses: list[str] = []
            params: list[Any] = []
            if device_id:
                clauses.append("device_id=?")
                params.append(device_id)
            if media_type:
                clauses.append("media_type=?")
                params.append(media_type)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = self._sqlite_rows(
                f"SELECT * FROM mobile_media {where} ORDER BY COALESCE(uploaded_at, created_at) DESC, id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            )
        else:
            params = {"order": "uploaded_at.desc.nullslast,created_at.desc", "limit": str(page_size), "offset": str(offset)}
            if device_id:
                params["device_id"] = f"eq.{device_id}"
            if media_type:
                params["media_type"] = f"eq.{media_type}"
            rows = self._get("mobile_media", params)
        return {"items": rows, "page": page, "page_size": page_size, "has_more": len(rows) == page_size}

    def list_otp_configurations(self) -> list[dict[str, Any]]:
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM otp_configurations ORDER BY priority, service_code")
        else:
            rows = self._get("otp_configurations", {"order": "priority.asc,service_code.asc"})
        return [self.decode_otp_configuration(row) for row in rows]

    def list_otp_filters(self, service_code: str = "", enabled_only: bool = False) -> list[dict[str, Any]]:
        if self.is_sqlite:
            clauses: list[str] = []
            params: list[Any] = []
            if service_code:
                clauses.append("service_code=?")
                params.append(service_code.strip().lower())
            if enabled_only:
                clauses.append("enabled=1")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = self._sqlite_rows(f"SELECT * FROM otp_filter_configurations {where} ORDER BY priority, id", tuple(params))
        else:
            params = {"order": "priority.asc,id.asc"}
            if service_code:
                params["service_code"] = f"eq.{service_code.strip().lower()}"
            if enabled_only:
                params["enabled"] = "eq.true"
            rows = self._get("otp_filter_configurations", params)
        return [self.decode_otp_filter(row) for row in rows]

    def decode_otp_filter(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["enabled"] = bool(item.get("enabled"))
        item["otp_length"] = int(item.get("otp_length") or 6)
        item["validity_seconds"] = int(item.get("validity_seconds") or 60)
        return item

    def save_otp_filter(self, payload: OtpFilterPayload) -> dict[str, Any]:
        now = self.now()
        data = payload.model_dump()
        filter_id = (data.get("filter_id") or data.get("service_code") or "onebss").strip().lower()
        row = {
            **data,
            "filter_id": filter_id,
            "service_code": str(data.get("service_code") or "onebss").strip().lower(),
            "sender_match_type": "exact" if data.get("sender_match_type") == "equals" else data.get("sender_match_type"),
            "otp_length": max(1, min(12, int(data.get("otp_length") or 6))),
            "validity_seconds": max(1, int(data.get("validity_seconds") or 60)),
            "updated_at": now,
        }
        if not row.get("created_at"):
            row["created_at"] = now
        if self.is_sqlite:
            values = {**row, "enabled": int(bool(row["enabled"]))}
            with self.base.connect() as connection:
                if values.get("id"):
                    connection.execute(
                        """
                        UPDATE otp_filter_configurations SET filter_id=?, rule_name=?, service_code=?, sender_pattern=?,
                          sender_match_type=?, otp_length=?, start_prefix=?, validity_seconds=?, enabled=?,
                          device_id=?, sim_slot=?, priority=?, updated_at=?
                        WHERE id=?
                        """,
                        (
                            values["filter_id"], values["rule_name"], values["service_code"], values["sender_pattern"],
                            values["sender_match_type"], values["otp_length"], values["start_prefix"], values["validity_seconds"],
                            values["enabled"], values["device_id"], values["sim_slot"], values["priority"], now, values["id"],
                        ),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO otp_filter_configurations
                        (filter_id, rule_name, service_code, sender_pattern, sender_match_type, otp_length,
                         start_prefix, validity_seconds, enabled, device_id, sim_slot, priority, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(filter_id) DO UPDATE SET
                          rule_name=excluded.rule_name,
                          service_code=excluded.service_code,
                          sender_pattern=excluded.sender_pattern,
                          sender_match_type=excluded.sender_match_type,
                          otp_length=excluded.otp_length,
                          start_prefix=excluded.start_prefix,
                          validity_seconds=excluded.validity_seconds,
                          enabled=excluded.enabled,
                          device_id=excluded.device_id,
                          sim_slot=excluded.sim_slot,
                          priority=excluded.priority,
                          updated_at=excluded.updated_at
                        """,
                        (
                            values["filter_id"], values["rule_name"], values["service_code"], values["sender_pattern"],
                            values["sender_match_type"], values["otp_length"], values["start_prefix"], values["validity_seconds"],
                            values["enabled"], values["device_id"], values["sim_slot"], values["priority"], now, now,
                        ),
                    )
            rows = self.list_otp_filters(service_code=values["service_code"])
            return next((item for item in rows if item.get("filter_id") == values["filter_id"]), row)
        row.pop("id", None)
        self._upsert("otp_filter_configurations", row, "filter_id")
        rows = self.list_otp_filters(service_code=row["service_code"])
        return next((item for item in rows if item.get("filter_id") == row["filter_id"]), row)

    def get_otp_configuration(self, service_code: str) -> dict[str, Any] | None:
        if self.is_sqlite:
            row = self._sqlite_one("SELECT * FROM otp_configurations WHERE service_code=?", (service_code,))
        else:
            rows = self._get("otp_configurations", {"service_code": f"eq.{service_code}", "limit": "1"})
            row = rows[0] if rows else None
        return self.decode_otp_configuration(row) if row else None

    def decode_otp_configuration(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        for field in ["enabled", "auto_fill_enabled", "manual_fallback_enabled"]:
            item[field] = bool(item.get(field))
        return item

    def save_otp_configuration(self, payload: OtpConfigurationPayload) -> dict[str, Any]:
        now = self.now()
        data = payload.model_dump()
        row = {**data, "service_code": data["service_code"].strip().lower(), "updated_at": now}
        if not row.get("created_at"):
            row["created_at"] = now
        if self.is_sqlite:
            values = {**row}
            for field in ["enabled", "auto_fill_enabled", "manual_fallback_enabled"]:
                values[field] = int(bool(values[field]))
            with self.base.connect() as connection:
                if values.get("id"):
                    connection.execute(
                        """
                        UPDATE otp_configurations SET service_code=?, service_name=?, enabled=?, source_type=?,
                          sender_pattern=?, sender_match_type=?, package_pattern=?, title_pattern=?, otp_regex=?,
                          otp_keyword=?, otp_length_min=?, otp_length_max=?, wait_timeout_seconds=?, validity_seconds=?,
                          device_id=?, sim_slot=?, auto_fill_enabled=?, manual_fallback_enabled=?, priority=?, updated_at=?
                        WHERE id=?
                        """,
                        (
                            values["service_code"], values["service_name"], values["enabled"], values["source_type"],
                            values["sender_pattern"], values["sender_match_type"], values["package_pattern"], values["title_pattern"],
                            values["otp_regex"], values["otp_keyword"], values["otp_length_min"], values["otp_length_max"],
                            values["wait_timeout_seconds"], values["validity_seconds"], values["device_id"], values["sim_slot"],
                            values["auto_fill_enabled"], values["manual_fallback_enabled"], values["priority"], now, values["id"],
                        ),
                    )
                    config_id = values["id"]
                else:
                    cursor = connection.execute(
                        """
                        INSERT INTO otp_configurations
                        (service_code, service_name, enabled, source_type, sender_pattern, sender_match_type,
                         package_pattern, title_pattern, otp_regex, otp_keyword, otp_length_min, otp_length_max,
                         wait_timeout_seconds, validity_seconds, device_id, sim_slot, auto_fill_enabled,
                         manual_fallback_enabled, priority, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(service_code) DO UPDATE SET
                          service_name=excluded.service_name, enabled=excluded.enabled, source_type=excluded.source_type,
                          sender_pattern=excluded.sender_pattern, sender_match_type=excluded.sender_match_type,
                          package_pattern=excluded.package_pattern, title_pattern=excluded.title_pattern,
                          otp_regex=excluded.otp_regex, otp_keyword=excluded.otp_keyword,
                          otp_length_min=excluded.otp_length_min, otp_length_max=excluded.otp_length_max,
                          wait_timeout_seconds=excluded.wait_timeout_seconds, validity_seconds=excluded.validity_seconds,
                          device_id=excluded.device_id, sim_slot=excluded.sim_slot,
                          auto_fill_enabled=excluded.auto_fill_enabled, manual_fallback_enabled=excluded.manual_fallback_enabled,
                          priority=excluded.priority, updated_at=excluded.updated_at
                        """,
                        (
                            values["service_code"], values["service_name"], values["enabled"], values["source_type"],
                            values["sender_pattern"], values["sender_match_type"], values["package_pattern"], values["title_pattern"],
                            values["otp_regex"], values["otp_keyword"], values["otp_length_min"], values["otp_length_max"],
                            values["wait_timeout_seconds"], values["validity_seconds"], values["device_id"], values["sim_slot"],
                            values["auto_fill_enabled"], values["manual_fallback_enabled"], values["priority"], now, now,
                        ),
                    )
                    config_id = cursor.lastrowid
            return self.get_otp_configuration(values["service_code"]) or {"id": config_id, **row}
        if row.get("id"):
            config_id = row.pop("id")
            self._patch("otp_configurations", {"id": f"eq.{config_id}"}, row)
        else:
            row.pop("id", None)
            self._upsert("otp_configurations", row, "service_code")
        return self.get_otp_configuration(row["service_code"]) or row

    def create_otp_request(self, service_code: str, job_id: str, configuration: dict[str, Any], timeout_seconds: int | None = None) -> dict[str, Any]:
        now = self.now()
        timeout = int(timeout_seconds or configuration.get("wait_timeout_seconds") or 120)
        row = {
            "request_id": f"OTP{uuid.uuid4().hex[:18].upper()}",
            "service_code": service_code,
            "job_id": job_id or "",
            "configuration_id": configuration.get("id"),
            "source_type": configuration.get("source_type") or "sms",
            "requested_at": now,
            "expires_at": self.from_now(timeout),
            "status": "waiting",
            "matched_source_type": None,
            "matched_source_id": None,
            "matched_at": None,
            "consumed_at": None,
            "cancelled_at": None,
            "failure_code": None,
            "code_encrypted": "",
            "code_masked": "",
            "created_at": now,
            "updated_at": now,
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO otp_requests
                    (request_id, service_code, job_id, configuration_id, source_type, requested_at, expires_at,
                     status, matched_source_type, matched_source_id, matched_at, consumed_at, cancelled_at,
                     failure_code, code_encrypted, code_masked, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting', NULL, NULL, NULL, NULL, NULL, NULL, '', '', ?, ?)
                    """,
                    (row["request_id"], row["service_code"], row["job_id"], row["configuration_id"], row["source_type"], row["requested_at"], row["expires_at"], row["created_at"], row["updated_at"]),
                )
                row["id"] = int(cursor.lastrowid)
        else:
            row = self._insert("otp_requests", row)
        self.add_otp_event(row["request_id"], "created", details={"service_code": service_code, "job_id": job_id})
        return self.decode_otp_request(row)

    def decode_otp_request(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item.pop("code_encrypted", None)
        return item

    def get_otp_request(self, request_id: str) -> dict[str, Any] | None:
        if self.is_sqlite:
            row = self._sqlite_one("SELECT * FROM otp_requests WHERE request_id=?", (request_id,))
        else:
            rows = self._get("otp_requests", {"request_id": f"eq.{request_id}", "limit": "1"})
            row = rows[0] if rows else None
        return row

    def list_otp_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM otp_requests ORDER BY requested_at DESC LIMIT ?", (limit,))
        else:
            rows = self._get("otp_requests", {"order": "requested_at.desc", "limit": str(limit)})
        return [self.decode_otp_request(row) for row in rows]

    def record_otp_latest(
        self,
        *,
        otp_filter: dict[str, Any],
        sender: str,
        code: str,
        received_at: str,
        source_type: str,
        source_id: str | int,
        request_id: str,
    ) -> None:
        now = self.now()
        try:
            received_dt = datetime.fromisoformat(str(received_at or now).replace("Z", "+00:00"))
        except ValueError:
            received_dt = datetime.now(UTC)
        expires_at = (received_dt + timedelta(seconds=int(otp_filter.get("validity_seconds") or 60))).isoformat(timespec="seconds")
        row = {
            "filter_id": str(otp_filter.get("filter_id") or otp_filter.get("service_code") or ""),
            "service_code": str(otp_filter.get("service_code") or ""),
            "rule_name": str(otp_filter.get("rule_name") or otp_filter.get("service_name") or ""),
            "sender": sender,
            "code_masked": str(code or ""),
            "received_at": received_at or now,
            "expires_at": expires_at,
            "status": "valid",
            "source_type": source_type,
            "source_id": str(source_id),
            "otp_request_id": request_id,
            "used_at": None,
            "created_at": now,
            "updated_at": now,
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO otp_latest_values
                    (filter_id, service_code, rule_name, sender, code_masked, received_at, expires_at, status,
                     source_type, source_id, otp_request_id, used_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'valid', ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        row["filter_id"], row["service_code"], row["rule_name"], row["sender"], row["code_masked"],
                        row["received_at"], row["expires_at"], row["source_type"], row["source_id"],
                        row["otp_request_id"], row["created_at"], row["updated_at"],
                    ),
                )
            return
        self._insert("otp_latest_values", row)

    def mark_otp_latest_used(self, request_id: str) -> None:
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "UPDATE otp_latest_values SET status='used', used_at=?, updated_at=? WHERE otp_request_id=? AND status!='used'",
                    (now, now, request_id),
                )
            return
        self._patch("otp_latest_values", {"otp_request_id": f"eq.{request_id}"}, {"status": "used", "used_at": now, "updated_at": now})

    def bind_otp_latest_to_request(self, latest_id: str | int, request_id: str) -> None:
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute(
                    "UPDATE otp_latest_values SET otp_request_id=?, updated_at=? WHERE id=? AND status='valid'",
                    (request_id, now, latest_id),
                )
            return
        self._patch("otp_latest_values", {"id": f"eq.{latest_id}", "status": "eq.valid"}, {"otp_request_id": request_id, "updated_at": now})

    def expire_otp_latest_values(self) -> int:
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                cursor = connection.execute("UPDATE otp_latest_values SET status='expired', updated_at=? WHERE status='valid' AND expires_at<?", (now, now))
                return int(cursor.rowcount or 0)
        rows = self._get("otp_latest_values", {"status": "eq.valid", "expires_at": f"lt.{now}", "select": "id"})
        for row in rows:
            self._patch("otp_latest_values", {"id": f"eq.{row['id']}"}, {"status": "expired", "updated_at": now})
        return len(rows)

    def list_otp_latest_values(self, limit: int = 100) -> list[dict[str, Any]]:
        self.expire_otp_latest_values()
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM otp_latest_values ORDER BY received_at DESC, id DESC LIMIT ?", (limit,))
        else:
            rows = self._get("otp_latest_values", {"order": "received_at.desc,id.desc", "limit": str(limit)})
        return rows

    def waiting_otp_requests(self, service_code: str = "") -> list[dict[str, Any]]:
        now = self.now()
        if self.is_sqlite:
            if service_code:
                rows = self._sqlite_rows("SELECT * FROM otp_requests WHERE status='waiting' AND service_code=? AND expires_at>=? ORDER BY requested_at", (service_code, now))
            else:
                rows = self._sqlite_rows("SELECT * FROM otp_requests WHERE status='waiting' AND expires_at>=? ORDER BY requested_at", (now,))
        else:
            params = {"status": "eq.waiting", "expires_at": f"gte.{now}", "order": "requested_at.asc"}
            if service_code:
                params["service_code"] = f"eq.{service_code}"
            rows = self._get("otp_requests", params)
        return rows

    def match_otp_request(self, request_id: str, source_type: str, source_id: str | int, code: str) -> bool:
        now = self.now()
        encrypted = security.encrypt_text(self.settings, code, "otp")
        payload = {
            "status": "matched",
            "matched_source_type": source_type,
            "matched_source_id": str(source_id),
            "matched_at": now,
            "code_encrypted": encrypted,
            "code_masked": str(code or ""),
            "updated_at": now,
        }
        if self.is_sqlite:
            with self.base.connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE otp_requests
                    SET status='matched', matched_source_type=?, matched_source_id=?, matched_at=?,
                        code_encrypted=?, code_masked=?, updated_at=?
                    WHERE request_id=? AND status='waiting'
                    """,
                    (source_type, str(source_id), now, encrypted, str(code or ""), now, request_id),
                )
                changed = cursor.rowcount > 0
        else:
            before = self.get_otp_request(request_id)
            if not before or before.get("status") != "waiting":
                return False
            self._patch("otp_requests", {"request_id": f"eq.{request_id}", "status": "eq.waiting"}, payload)
            changed = True
        if changed:
            self.add_otp_event(request_id, "matched", source_type=source_type, source_id=str(source_id))
        return changed

    def consume_otp_request(self, request_id: str) -> str:
        row = self.get_otp_request(request_id)
        if not row or row.get("status") != "matched":
            return ""
        code = security.decrypt_text(self.settings, row.get("code_encrypted") or "", "otp")
        if not code:
            return ""
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute("UPDATE otp_requests SET status='consumed', consumed_at=?, updated_at=? WHERE request_id=? AND status='matched'", (now, now, request_id))
        else:
            self._patch("otp_requests", {"request_id": f"eq.{request_id}", "status": "eq.matched"}, {"status": "consumed", "consumed_at": now, "updated_at": now})
        source_type = row.get("matched_source_type") or ""
        source_id = row.get("matched_source_id") or ""
        if source_type == "sms" and source_id:
            self.mark_sms_matched(source_id, request_id, used=True)
        if source_type == "notification" and source_id:
            self.mark_notification_matched(source_id, request_id, used=True)
        self.mark_otp_latest_used(request_id)
        self.add_otp_event(request_id, "consumed", source_type=source_type, source_id=source_id)
        return code

    def cancel_otp_request(self, request_id: str, reason: str = "cancelled") -> None:
        now = self.now()
        payload = {"status": "cancelled", "cancelled_at": now, "failure_code": reason, "updated_at": now}
        if self.is_sqlite:
            with self.base.connect() as connection:
                connection.execute("UPDATE otp_requests SET status='cancelled', cancelled_at=?, failure_code=?, updated_at=? WHERE request_id=? AND status IN ('waiting','matched')", (now, reason, now, request_id))
        else:
            self._patch("otp_requests", {"request_id": f"eq.{request_id}"}, payload)
        self.add_otp_event(request_id, "cancelled", details={"reason": reason})

    def expire_otp_requests(self) -> int:
        now = self.now()
        if self.is_sqlite:
            with self.base.connect() as connection:
                cursor = connection.execute("UPDATE otp_requests SET status='expired', failure_code='timeout', updated_at=? WHERE status='waiting' AND expires_at<?", (now, now))
                return int(cursor.rowcount or 0)
        rows = self._get("otp_requests", {"status": "eq.waiting", "expires_at": f"lt.{now}", "select": "request_id"})
        for row in rows:
            self._patch("otp_requests", {"request_id": f"eq.{row['request_id']}"}, {"status": "expired", "failure_code": "timeout", "updated_at": now})
        return len(rows)

    def add_otp_event(self, request_id: str, event_type: str, source_type: str = "", source_id: str = "", details: dict[str, Any] | None = None) -> None:
        row = {
            "request_id": request_id,
            "event_type": event_type,
            "source_type": source_type,
            "source_id": str(source_id or ""),
            "details": details or {},
            "created_at": self.now(),
        }
        try:
            if self.is_sqlite:
                with self.base.connect() as connection:
                    connection.execute(
                        "INSERT INTO otp_events (request_id, event_type, source_type, source_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (row["request_id"], row["event_type"], row["source_type"], row["source_id"], json.dumps(row["details"], ensure_ascii=False), row["created_at"]),
                    )
            else:
                self._insert("otp_events", row)
        except Exception:
            return

    def list_otp_events(self, limit: int = 100) -> list[dict[str, Any]]:
        if self.is_sqlite:
            rows = self._sqlite_rows("SELECT * FROM otp_events ORDER BY created_at DESC LIMIT ?", (limit,))
        else:
            rows = self._get("otp_events", {"order": "created_at.desc", "limit": str(limit)})
        for row in rows:
            row["details"] = self._json_loads(row.get("details"), {})
        return rows

    def overview_counts(self, online_threshold_seconds: int) -> dict[str, Any]:
        devices = self.list_devices()
        cutoff = datetime.now(UTC) - timedelta(seconds=online_threshold_seconds)
        online = 0
        versions: dict[str, int] = {}
        for device in devices:
            if device.get("app_version"):
                versions[str(device["app_version"])] = versions.get(str(device["app_version"]), 0) + 1
            last_seen = str(device.get("last_seen_at") or "")
            try:
                parsed = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                if parsed >= cutoff and device.get("is_active"):
                    online += 1
            except ValueError:
                pass
        today = datetime.now(UTC).date().isoformat()
        if self.is_sqlite:
            sms_today = self._sqlite_one("SELECT COUNT(*) AS total FROM mobile_sms_messages WHERE received_at>=?", (today,)) or {"total": 0}
            otp_today = self._sqlite_one("SELECT COUNT(*) AS total FROM otp_requests WHERE requested_at>=?", (today,)) or {"total": 0}
            otp_success = self._sqlite_one("SELECT COUNT(*) AS total FROM otp_requests WHERE requested_at>=? AND status='consumed'", (today,)) or {"total": 0}
            otp_timeout = self._sqlite_one("SELECT COUNT(*) AS total FROM otp_requests WHERE requested_at>=? AND status='expired'", (today,)) or {"total": 0}
            pending = self._sqlite_one("SELECT COUNT(*) AS total FROM mobile_commands WHERE status IN ('pending','delivered')", ()) or {"total": 0}
        else:
            sms_today = {"total": len(self._get("mobile_sms_messages", {"received_at": f"gte.{today}", "select": "id"}))}
            otp_today = {"total": len(self._get("otp_requests", {"requested_at": f"gte.{today}", "select": "id"}))}
            otp_success = {"total": len(self._get("otp_requests", {"requested_at": f"gte.{today}", "status": "eq.consumed", "select": "id"}))}
            otp_timeout = {"total": len(self._get("otp_requests", {"requested_at": f"gte.{today}", "status": "eq.expired", "select": "id"}))}
            pending = {"total": len(self._get("mobile_commands", {"status": "in.(pending,delivered)", "select": "command_id"}))}
        recent_sms = self.list_sms(page=1, page_size=5)["items"]
        return {
            "devices_online": online,
            "devices_offline": max(0, len(devices) - online),
            "sms_today": int(sms_today.get("total") or 0),
            "otp_today": int(otp_today.get("total") or 0),
            "otp_success": int(otp_success.get("total") or 0),
            "otp_timeout": int(otp_timeout.get("total") or 0),
            "pending_commands": int(pending.get("total") or 0),
            "device_alerts": sum(1 for device in devices if not device.get("is_active")),
            "app_versions": versions,
            "recent_sms": recent_sms,
        }
