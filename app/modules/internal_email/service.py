from __future__ import annotations

import imaplib
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.policy import default
from email.utils import parsedate_to_datetime, parseaddr
from html.parser import HTMLParser
from typing import Any

from app.modules.internal_email.repository import InternalEmailRepository
from app.modules.mobile_gateway import security
from app.modules.mobile_gateway.otp_service import OtpService
from app.modules.mobile_gateway.repository import MobileGatewayRepository
from app.settings import Settings


DEFAULT_CONNECTION_CODE = "internal_email"
DEFAULT_MAILBOX = "INBOX"
DEFAULT_HOST = "email.vnpt.vn"
DEFAULT_PORT = 993
DEFAULT_OTP_RULES_KEY = "otp_rules"
EMAIL_ADDRESS_PATTERN = re.compile(r"\b[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}\b")


class InternalEmailConfigurationError(RuntimeError):
    pass


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


@dataclass(frozen=True)
class InternalEmailConfig:
    enabled: bool
    account_key: str
    host: str
    port: int
    use_ssl: bool
    username: str
    password: str
    mailbox: str
    timeout_seconds: int
    sync_interval_seconds: int
    lookback_minutes: int
    max_messages: int

    def public_details(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "account_key": self.account_key,
            "host": self.host,
            "port": self.port,
            "use_ssl": self.use_ssl,
            "mailbox": self.mailbox,
            "username_configured": bool(self.username),
            "password_configured": bool(self.password),
            "timeout_seconds": self.timeout_seconds,
            "sync_interval_seconds": self.sync_interval_seconds,
            "lookback_minutes": self.lookback_minutes,
            "max_messages": self.max_messages,
        }


def _secret_text(settings: Settings, name: str) -> str:
    value = getattr(settings, name, "")
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value().strip()
    return str(value or "").strip()


def _bool_value(value: Any, default_value: bool = False) -> bool:
    if value in (None, ""):
        return default_value
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_value(value: Any, default_value: int, minimum: int = 1, maximum: int = 10_000) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default_value
    return min(max(number, minimum), maximum)


def _connection_config(connection: dict[str, Any] | None) -> dict[str, Any]:
    config = (connection or {}).get("config") or {}
    return config if isinstance(config, dict) else {}


def resolve_internal_email_config(settings: Settings, connection: dict[str, Any] | None = None) -> InternalEmailConfig:
    config = _connection_config(connection)
    password_env = str(config.get("password_env") or "INTERNAL_EMAIL_PASSWORD").strip()
    password = (
        str(config.get("password") or "").strip()
        or (os.getenv(password_env, "").strip() if password_env else "")
        or _secret_text(settings, "internal_email_password")
    )
    username = str(config.get("username") or getattr(settings, "internal_email_username", "") or "").strip()
    host = str(config.get("host") or getattr(settings, "internal_email_host", DEFAULT_HOST) or DEFAULT_HOST).strip()
    mailbox = str(config.get("mailbox") or getattr(settings, "internal_email_mailbox", DEFAULT_MAILBOX) or DEFAULT_MAILBOX).strip()
    enabled_default = _bool_value(getattr(settings, "internal_email_sync_enabled", False), False)
    if connection:
        enabled = bool(connection.get("is_active"))
    else:
        enabled = enabled_default
    return InternalEmailConfig(
        enabled=enabled,
        account_key=str(config.get("account_key") or DEFAULT_CONNECTION_CODE).strip() or DEFAULT_CONNECTION_CODE,
        host=host,
        port=_int_value(config.get("port") or getattr(settings, "internal_email_port", DEFAULT_PORT), DEFAULT_PORT, 1, 65535),
        use_ssl=_bool_value(config.get("use_ssl"), True),
        username=username,
        password=password,
        mailbox=mailbox or DEFAULT_MAILBOX,
        timeout_seconds=_int_value(config.get("timeout_seconds") or getattr(settings, "internal_email_timeout_seconds", 20), 20, 3, 120),
        sync_interval_seconds=_int_value(config.get("sync_interval_seconds") or getattr(settings, "internal_email_sync_interval_seconds", 30), 30, 15, 3600),
        lookback_minutes=_int_value(config.get("lookback_minutes") or getattr(settings, "internal_email_lookback_minutes", 30), 30, 1, 1440),
        max_messages=_int_value(config.get("max_messages") or getattr(settings, "internal_email_max_messages", 40), 40, 1, 200),
    )


class InternalEmailSyncService:
    def __init__(self, base_repository: Any, settings: Settings, connection: dict[str, Any] | None = None) -> None:
        self.base_repository = base_repository
        self.settings = settings
        self.connection = connection if connection is not None else self._load_connection()
        self.config = resolve_internal_email_config(settings, self.connection)
        self.email_repository = InternalEmailRepository(base_repository)
        self.mobile_repository = MobileGatewayRepository(base_repository, settings)
        self.otp_service = OtpService(self.mobile_repository)

    def _load_connection(self) -> dict[str, Any] | None:
        getter = getattr(self.base_repository, "get_system_connection_by_code", None)
        if not getter:
            return None
        return getter(DEFAULT_CONNECTION_CODE)

    def status(self) -> dict[str, Any]:
        try:
            messages = self.email_repository.list_messages(limit=1)
            latest_message_at = messages[0].get("received_at") if messages else None
        except RuntimeError as error:
            return {
                "ok": False,
                "message": "internal_email_messages schema is missing.",
                "details": {**self.config.public_details(), "schema_error": str(error)[:240]},
            }
        return {
            "ok": True,
            "message": "Internal email sync is configured." if self.config.enabled else "Internal email sync is inactive.",
            "details": {**self.config.public_details(), "latest_message_at": latest_message_at},
        }

    def test_connection(self) -> dict[str, Any]:
        missing = self._missing_config_fields()
        if missing:
            return {
                "ok": False,
                "message": "Internal email config is incomplete.",
                "details": {**self.config.public_details(), "missing": missing},
            }
        client = None
        try:
            client = self._connect()
            select_status, select_data = client.select(self.config.mailbox, readonly=True)
            if select_status != "OK":
                return {
                    "ok": False,
                    "message": "IMAP login ok but mailbox cannot be opened.",
                    "details": {**self.config.public_details(), "select": _safe_imap_data(select_data)},
                }
            return {
                "ok": True,
                "message": "IMAP internal email connection is ready.",
                "details": {**self.config.public_details(), "mailbox_status": _safe_imap_data(select_data)},
            }
        except (OSError, TimeoutError, imaplib.IMAP4.error) as error:
            return {
                "ok": False,
                "message": "Cannot connect to internal email IMAP.",
                "details": {**self.config.public_details(), "error": str(error)[:240]},
            }
        finally:
            _logout_quietly(client)

    def sync_once(self, refresh_existing: bool = False) -> dict[str, Any]:
        if not self.config.enabled:
            return {"ok": True, "message": "Internal email sync is inactive.", "details": self.config.public_details()}
        missing = self._missing_config_fields()
        if missing:
            return {
                "ok": False,
                "message": "Internal email config is incomplete.",
                "details": {**self.config.public_details(), "missing": missing},
            }
        client = None
        fetched = saved = refreshed = skipped = otp_records = otp_matches = 0
        try:
            self.mobile_repository.ensure_defaults()
            client = self._connect()
            select_status, select_data = client.select(self.config.mailbox, readonly=True)
            if select_status != "OK":
                raise InternalEmailConfigurationError(f"Cannot open mailbox {self.config.mailbox}: {_safe_imap_data(select_data)}")
            otp_rules = list_internal_email_otp_rules(self.base_repository)
            for uid in self._recent_uids(client):
                existing_message = self.email_repository.get_message_by_uid(self.config.account_key, self.config.mailbox, uid)
                if existing_message and not refresh_existing:
                    skipped += 1
                    continue
                raw_message = self._fetch_message(client, uid)
                if not raw_message:
                    skipped += 1
                    continue
                fetched += 1
                parsed = parse_email_message(raw_message, uid, otp_rules=otp_rules)
                saved_message, created = self.email_repository.save_message(
                    {
                        "account_key": self.config.account_key,
                        "mailbox": self.config.mailbox,
                        "uid": uid,
                        **parsed["metadata"],
                    }
                )
                if created:
                    saved += 1
                else:
                    refreshed += 1
                otp_result = self._process_otp(saved_message, parsed["search_text"])
                if otp_result:
                    otp_records += int(otp_result.get("recorded") or 0)
                    otp_matches += int(otp_result.get("matched") or 0)
            return {
                "ok": True,
                "message": f"Internal email sync finished: saved={saved}, refreshed={refreshed}, otp={otp_records}.",
                "details": {
                    **self.config.public_details(),
                    "fetched": fetched,
                    "saved": saved,
                    "refreshed": refreshed,
                    "skipped": skipped,
                    "otp_records": otp_records,
                    "otp_matches": otp_matches,
                    "refresh_existing": bool(refresh_existing),
                },
            }
        except (OSError, TimeoutError, imaplib.IMAP4.error, RuntimeError, InternalEmailConfigurationError) as error:
            return {
                "ok": False,
                "message": "Internal email sync failed.",
                "details": {**self.config.public_details(), "error": str(error)[:300]},
            }
        finally:
            _logout_quietly(client)

    def _missing_config_fields(self) -> list[str]:
        missing = []
        if not self.config.host:
            missing.append("host")
        if not self.config.username:
            missing.append("username")
        if not self.config.password:
            missing.append("password")
        if not self.config.mailbox:
            missing.append("mailbox")
        return missing

    def _connect(self) -> imaplib.IMAP4:
        if self.config.use_ssl:
            client: imaplib.IMAP4 = imaplib.IMAP4_SSL(self.config.host, self.config.port, timeout=self.config.timeout_seconds)
        else:
            client = imaplib.IMAP4(self.config.host, self.config.port, timeout=self.config.timeout_seconds)
        client.login(self.config.username, self.config.password)
        return client

    def _recent_uids(self, client: imaplib.IMAP4) -> list[str]:
        since = (datetime.now(UTC) - timedelta(minutes=self.config.lookback_minutes)).strftime("%d-%b-%Y")
        status, data = client.uid("SEARCH", None, "SINCE", since)
        if status != "OK" or not data:
            return []
        raw_uids = data[0].split() if isinstance(data[0], (bytes, bytearray)) else str(data[0] or "").encode().split()
        uids = sorted({_decode_ascii(uid) for uid in raw_uids if uid}, key=_uid_sort_key, reverse=True)
        return uids[: self.config.max_messages]

    @staticmethod
    def _fetch_message(client: imaplib.IMAP4, uid: str) -> bytes:
        status, data = client.uid("FETCH", uid, "(RFC822)")
        if status != "OK":
            return b""
        for item in data or []:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
                return bytes(item[1])
        return b""

    def _process_otp(self, message: dict[str, Any], search_text: str) -> dict[str, int] | None:
        sender = str(message.get("sender") or message.get("sender_email") or "")
        received_at = str(message.get("received_at") or "")
        message_id = str(message.get("id") or message.get("uid") or "")
        known_code = str(message.get("otp_code") or "").strip()
        body_for_record = f"{known_code}\n{search_text}" if known_code else search_text
        result = self.otp_service.record_latest_from_email(
            {
                "id": message_id,
                "sender": sender,
                "sender_email": message.get("sender_email") or "",
                "subject": message.get("subject") or "",
                "body": body_for_record,
                "received_at": received_at,
            }
        )
        if not result:
            return None
        code = known_code or str(result.get("code") or "")
        request_id = str(result.get("request_id") or "")
        self.email_repository.mark_message_otp(
            message_id,
            str(result.get("filter_id") or result.get("service_code") or ""),
            code,
            security.code_mask(code),
            request_id,
        )
        return {"recorded": 1, "matched": 1 if request_id else 0}


def parse_email_message(raw_message: bytes, uid: str, otp_rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    message = message_from_bytes(raw_message, policy=default)
    subject = _header_text(message.get("Subject", ""))
    sender_header = _header_text(message.get("From", ""))
    sender_name, sender_email = parseaddr(sender_header)
    sender = sender_name or sender_email or sender_header
    body = _message_body_text(message)
    received_at = _message_datetime(message.get("Date"))
    search_text = "\n".join(part for part in (subject, sender, sender_email, body) if part)
    otp_code = extract_internal_email_otp(
        subject=subject,
        body=body,
        sender=sender,
        sender_email=sender_email,
        otp_rules=otp_rules or [],
    )
    return {
        "metadata": {
            "uid": uid,
            "message_id": str(message.get("Message-ID") or "").strip(),
            "sender": sender,
            "sender_email": sender_email,
            "subject": subject,
            "body_masked": _safe_preview(body),
            "received_at": received_at,
            "synced_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "is_otp_candidate": bool(otp_code),
            "otp_code": otp_code,
            "otp_code_masked": "*" * len(otp_code) if otp_code else "",
        },
        "search_text": search_text,
    }


def test_internal_email_connection(settings: Settings, repository: Any, connection: dict[str, Any] | None = None) -> dict[str, Any]:
    return InternalEmailSyncService(repository, settings, connection).test_connection()


def internal_email_status(repository: Any, settings: Settings) -> dict[str, Any]:
    return InternalEmailSyncService(repository, settings).status()


def sync_internal_email_once(repository: Any, settings: Settings) -> dict[str, Any]:
    return InternalEmailSyncService(repository, settings).sync_once()


def refresh_existing_internal_email_messages(repository: Any, settings: Settings) -> dict[str, Any]:
    return InternalEmailSyncService(repository, settings).sync_once(refresh_existing=True)


def list_internal_email_messages(repository: Any, limit: int = 20, otp_only: bool = False) -> list[dict[str, Any]]:
    return InternalEmailRepository(repository).list_messages(limit=limit, otp_only=otp_only)


def list_internal_email_otp_rules(repository: Any) -> list[dict[str, Any]]:
    connection = _internal_email_connection(repository)
    config = _connection_config(connection)
    raw_rules = config.get(DEFAULT_OTP_RULES_KEY)
    if not isinstance(raw_rules, list):
        return []
    return [_normalize_otp_rule(rule) for rule in raw_rules if isinstance(rule, dict)]


def save_internal_email_otp_rule(repository: Any, payload: dict[str, Any], actor: str = "") -> dict[str, Any]:
    rule = _normalize_otp_rule(payload)
    if not rule["sender_pattern"]:
        raise ValueError("sender_pattern is required")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    incoming_id = rule.get("id")
    if not rule.get("id"):
        rule["id"] = uuid.uuid4().hex
        rule["created_at"] = now
    rule["updated_at"] = now
    if actor and not rule.get("created_by"):
        rule["created_by"] = actor
    connection = _internal_email_connection(repository) or {}
    config = dict(_connection_config(connection))
    rules = list_internal_email_otp_rules(repository)
    replaced = False
    for index, existing in enumerate(rules):
        same_id = rule["id"] and str(existing.get("id") or "") == rule["id"]
        same_sender = (
            not incoming_id
            and str(existing.get("sender_pattern") or "").strip().lower() == rule["sender_pattern"].lower()
        )
        if same_id or same_sender:
            rules[index] = {**existing, **rule, "created_at": existing.get("created_at") or rule.get("created_at") or now}
            replaced = True
            rule = rules[index]
            break
    if not replaced:
        rules.append(rule)
    config[DEFAULT_OTP_RULES_KEY] = sorted(rules, key=lambda item: (int(item.get("priority") or 100), str(item.get("sender_pattern") or "")))
    _save_internal_email_connection(repository, connection, config)
    return rule


def delete_internal_email_otp_rule(repository: Any, rule_id: str) -> None:
    safe_id = str(rule_id or "").strip()
    if not safe_id:
        return
    connection = _internal_email_connection(repository) or {}
    config = dict(_connection_config(connection))
    rules = [rule for rule in list_internal_email_otp_rules(repository) if str(rule.get("id") or "") != safe_id]
    config[DEFAULT_OTP_RULES_KEY] = rules
    _save_internal_email_connection(repository, connection, config)


def extract_internal_email_otp(
    *,
    subject: str = "",
    body: str = "",
    sender: str = "",
    sender_email: str = "",
    otp_rules: list[dict[str, Any]] | None = None,
) -> str:
    search_text = "\n".join(part for part in (subject, body) if str(part or "").strip())
    for rule in sorted((otp_rules or []), key=lambda item: int(item.get("priority") or 100)):
        if not rule.get("enabled", True):
            continue
        if not _sender_matches_rule(rule, sender, sender_email):
            continue
        code = _extract_otp_with_rule(search_text, rule)
        if code:
            return code
    clean_body = _strip_email_noise(body)
    clean_subject = _strip_email_noise(subject)
    if not _looks_like_otp_text(f"{clean_subject}\n{clean_body}"):
        return ""
    return (
        security.extract_otp(clean_body, security.OTP_DIGIT_PATTERN.pattern)
        or security.extract_otp(clean_subject, security.OTP_DIGIT_PATTERN.pattern)
        or ""
    )


def _extract_otp_with_rule(text: str, rule: dict[str, Any]) -> str:
    search_text = str(text or "")
    regex = str(rule.get("regex") or rule.get("otp_regex") or "").strip()
    if regex:
        try:
            match = re.search(regex, search_text, re.IGNORECASE | re.MULTILINE)
        except re.error:
            match = None
        if match:
            raw = match.group(1) if match.groups() else match.group(0)
            code = re.sub(r"\D+", "", raw)
            if code:
                return code[:12]
    matches = [match.group(0) for match in re.finditer(r"\d+", search_text)]
    if str(rule.get("direction") or "left_to_right") in {"right_to_left", "rtl", "end"}:
        matches.reverse()
    if not matches:
        return ""
    occurrence = _bounded_int(rule.get("occurrence_index"), 1, 1, 200)
    if occurrence > len(matches):
        return ""
    candidate = matches[occurrence - 1]
    start = _bounded_int(rule.get("start_position"), 1, 1, max(len(candidate), 1))
    length = _bounded_int(rule.get("otp_length"), 6, 1, 12)
    if str(rule.get("direction") or "left_to_right") in {"right_to_left", "rtl", "end"}:
        end_index = max(len(candidate) - start + 1, 0)
        start_index = max(end_index - length, 0)
        code = candidate[start_index:end_index]
    else:
        start_index = start - 1
        code = candidate[start_index : start_index + length]
    return code if code.isdigit() and len(code) == length else ""


def _sender_matches_rule(rule: dict[str, Any], sender: str, sender_email: str) -> bool:
    pattern = str(rule.get("sender_pattern") or "").strip()
    if not pattern:
        return True
    raw_sender = " ".join(part for part in (sender, sender_email) if str(part or "").strip())
    normalized_sender = security.normalize_sender(raw_sender)
    normalized_pattern = security.normalize_sender(pattern)
    match_type = str(rule.get("sender_match_type") or "contains")
    if match_type in {"exact", "equals"}:
        return normalized_sender == normalized_pattern or security.normalize_sender(sender_email) == normalized_pattern
    if match_type == "regex":
        try:
            return bool(re.search(pattern, raw_sender, re.IGNORECASE))
        except re.error:
            return False
    return normalized_pattern in normalized_sender


def _normalize_otp_rule(rule: dict[str, Any]) -> dict[str, Any]:
    direction = str(rule.get("direction") or "left_to_right").strip().lower()
    if direction in {"rtl", "right", "end", "right_to_left"}:
        direction = "right_to_left"
    else:
        direction = "left_to_right"
    match_type = str(rule.get("sender_match_type") or "contains").strip().lower()
    if match_type == "equals":
        match_type = "exact"
    if match_type not in {"contains", "exact", "regex"}:
        match_type = "contains"
    return {
        "id": str(rule.get("id") or "").strip(),
        "sender_pattern": str(rule.get("sender_pattern") or "").strip(),
        "sender_match_type": match_type,
        "label": str(rule.get("label") or "").strip(),
        "direction": direction,
        "occurrence_index": _bounded_int(rule.get("occurrence_index"), 1, 1, 200),
        "start_position": _bounded_int(rule.get("start_position"), 1, 1, 500),
        "otp_length": _bounded_int(rule.get("otp_length"), 6, 1, 12),
        "regex": str(rule.get("regex") or rule.get("otp_regex") or "").strip(),
        "priority": _bounded_int(rule.get("priority"), 100, 0, 10_000),
        "enabled": _bool_value(rule.get("enabled"), True),
        "created_by": str(rule.get("created_by") or "").strip(),
        "created_at": str(rule.get("created_at") or "").strip(),
        "updated_at": str(rule.get("updated_at") or "").strip(),
    }


def _strip_email_noise(text: str) -> str:
    return EMAIL_ADDRESS_PATTERN.sub(" ", str(text or ""))


def _looks_like_otp_text(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(
        keyword in normalized
        for keyword in (
            "otp",
            " ma ",
            " mã ",
            "code",
            "xac thuc",
            "xác thực",
            "verification",
            "verify",
            "token",
            "pin",
        )
    )


def _bounded_int(value: Any, default_value: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default_value
    return min(max(number, minimum), maximum)


def _internal_email_connection(repository: Any) -> dict[str, Any] | None:
    getter = getattr(repository, "get_system_connection_by_code", None)
    if not getter:
        return None
    return getter(DEFAULT_CONNECTION_CODE)


def _save_internal_email_connection(repository: Any, connection: dict[str, Any] | None, config: dict[str, Any]) -> None:
    upsert = getattr(repository, "upsert_system_connection", None)
    if not upsert:
        raise RuntimeError("Repository does not support system connection updates.")
    upsert(
        DEFAULT_CONNECTION_CODE,
        str((connection or {}).get("name") or "Email nội bộ VNPT"),
        "internal_email",
        str((connection or {}).get("description") or "Đồng bộ hộp thư nội bộ qua IMAP để phát hiện OTP."),
        config,
        bool((connection or {}).get("is_active")),
    )


def _message_body_text(message: Message | EmailMessage) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart() or part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            text = _part_text(part)
            if not text:
                continue
            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(_html_to_text(text))
    else:
        text = _part_text(message)
        if message.get_content_type() == "text/html":
            html_parts.append(_html_to_text(text))
        else:
            plain_parts.append(text)
    return "\n".join(plain_parts or html_parts).strip()


def _part_text(part: Message | EmailMessage) -> str:
    try:
        content = part.get_content()
        if isinstance(content, str):
            return content.strip()
    except Exception:
        pass
    payload = part.get_payload(decode=True)
    if not isinstance(payload, (bytes, bytearray)):
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace").strip()
    except LookupError:
        return payload.decode("utf-8", errors="replace").strip()


def _html_to_text(html: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(str(html or ""))
    return parser.text()


def _header_text(value: Any) -> str:
    try:
        return str(make_header(decode_header(str(value or "")))).strip()
    except Exception:
        return str(value or "").strip()


def _message_datetime(value: Any) -> str:
    try:
        parsed = parsedate_to_datetime(str(value or ""))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(UTC).isoformat(timespec="seconds")


def _safe_preview(text: str, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _decode_ascii(value: bytes | bytearray | str) -> str:
    if isinstance(value, str):
        return value
    return bytes(value).decode("ascii", errors="ignore")


def _uid_sort_key(value: str) -> tuple[int, str]:
    try:
        return (int(value), value)
    except ValueError:
        return (0, value)


def _safe_imap_data(data: Any) -> str:
    return _safe_preview(" ".join(_decode_ascii(item) if isinstance(item, (bytes, bytearray)) else str(item) for item in (data or [])), 300)


def _logout_quietly(client: imaplib.IMAP4 | None) -> None:
    if not client:
        return
    try:
        client.close()
    except Exception:
        pass
    try:
        client.logout()
    except Exception:
        pass
