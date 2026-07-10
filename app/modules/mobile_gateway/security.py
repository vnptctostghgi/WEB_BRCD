from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, status

from app.settings import Settings


OTP_DIGIT_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


def _secret_value(settings: Settings, name: str, fallback: str = "") -> str:
    value = getattr(settings, name, fallback)
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value().strip()
    return str(value or "").strip()


def _base_secret(settings: Settings, purpose: str = "mobile") -> str:
    if purpose == "otp":
        configured = _secret_value(settings, "otp_encryption_key")
        if configured:
            return configured
    configured = _secret_value(settings, "mobile_gateway_master_key")
    if configured:
        return configured
    return settings.session_secret.get_secret_value()


def _fernet(settings: Settings, purpose: str = "mobile") -> Fernet:
    raw = _base_secret(settings, purpose).encode("utf-8")
    if len(raw) == 44:
        try:
            return Fernet(raw)
        except ValueError:
            pass
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))


def encrypt_text(settings: Settings, value: str, purpose: str = "mobile") -> str:
    if value is None:
        value = ""
    return _fernet(settings, purpose).encrypt(str(value).encode("utf-8")).decode("ascii")


def decrypt_text(settings: Settings, value: str, purpose: str = "mobile") -> str:
    if not value:
        return ""
    try:
        return _fernet(settings, purpose).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def generate_pairing_code() -> str:
    return f"{secrets.randbelow(10_000_000):07d}-{secrets.randbelow(10):01d}"


def pairing_code_hash(settings: Settings, code: str) -> str:
    normalized = re.sub(r"\s+", "", str(code or "")).upper()
    key = _base_secret(settings, "mobile").encode("utf-8")
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_device_secret() -> str:
    return secrets.token_urlsafe(32)


def normalize_sender(sender: str) -> str:
    return re.sub(r"\s+", "", str(sender or "").strip()).upper()


def mask_otp_text(text: str, otp_regex: str | None = None) -> str:
    pattern = OTP_DIGIT_PATTERN
    if otp_regex:
        try:
            pattern = re.compile(otp_regex)
        except re.error:
            pattern = OTP_DIGIT_PATTERN

    def repl(match: re.Match[str]) -> str:
        code = match.group(1) if match.groups() else match.group(0)
        return match.group(0).replace(code, "*" * len(code))

    return pattern.sub(repl, str(text or ""))


def code_mask(code: str) -> str:
    code = str(code or "")
    if len(code) <= 2:
        return "*" * len(code)
    return f"{code[0]}{'*' * max(0, len(code) - 2)}{code[-1]}"


def extract_otp(text: str, otp_regex: str, min_len: int = 4, max_len: int = 8, keyword: str = "") -> str:
    if keyword and keyword.lower() not in str(text or "").lower():
        return ""
    try:
        pattern = re.compile(otp_regex or OTP_DIGIT_PATTERN.pattern)
    except re.error:
        return ""
    for match in pattern.finditer(str(text or "")):
        code = match.group(1) if match.groups() else match.group(0)
        if code.isdigit() and min_len <= len(code) <= max_len:
            return code
    return ""


def parse_device_timestamp(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        number = int(raw)
        if number > 10_000_000_000:
            number = number // 1000
        return datetime.fromtimestamp(number, tz=UTC)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def verify_body_hash(body: bytes, provided: str) -> bool:
    digest_hex = hashlib.sha256(body).hexdigest()
    digest_b64 = base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")
    provided_text = str(provided or "").strip()
    return hmac.compare_digest(digest_hex, provided_text.lower()) or hmac.compare_digest(digest_b64, provided_text)


def verify_signature(secret: str, canonical: str, provided: str) -> bool:
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, str(provided or ""))


def generic_auth_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Device authentication failed.")


async def read_request_body(request: Request) -> bytes:
    return await request.body()


def safe_public_device(device: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in device.items() if "secret" not in key.lower()}
