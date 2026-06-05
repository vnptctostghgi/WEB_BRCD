import base64
import hashlib
import sqlite3
from typing import Any
from urllib.parse import urlparse

from cryptography.fernet import Fernet

from app.data_access.app_repository import AppRepository


class VaultService:
    def __init__(self, repository: AppRepository, secret: str) -> None:
        self.repository = repository
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self.cipher = Fernet(key)

    def save_website(self, actor: str, website_id: int | None, name: str, url: str, requires_otp: bool, is_active: bool) -> dict[str, Any]:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not name.strip():
            raise ValueError("Tên website và địa chỉ http/https hợp lệ là bắt buộc.")
        try:
            saved_id = self.repository.save_website(website_id, name.strip(), url.strip(), requires_otp, is_active)
        except sqlite3.IntegrityError as error:
            raise ValueError("Tên website đã tồn tại.") from error
        self.repository.add_audit_log(actor, "website_catalog_saved", f"Lưu danh mục website {name.strip()}")
        return self.repository.get_website(saved_id) or {}

    def save_credential(self, user: dict, credential_id: int | None, website_id: int, username: str, password: str, notes: str) -> None:
        website = self.repository.get_website(website_id)
        if not website or not website["is_active"]:
            raise ValueError("Website không tồn tại hoặc đã ngừng sử dụng.")
        if not username.strip() or not password:
            raise ValueError("Tài khoản và mật khẩu không được để trống.")
        encrypted = self.cipher.encrypt(password.encode("utf-8")).decode("ascii")
        self.repository.save_credential(credential_id, user["id"], website_id, username.strip(), encrypted, notes.strip())
        self.repository.add_audit_log(user["username"], "web_credential_saved", f"Lưu tài khoản cho {website['name']}")

    def reveal_password(self, user: dict, credential_id: int) -> str:
        credential = self.repository.get_credential(credential_id, user["id"])
        if not credential:
            raise ValueError("Không tìm thấy tài khoản web.")
        self.repository.add_audit_log(user["username"], "web_password_revealed", f"Xem mật khẩu tài khoản web #{credential_id}")
        return self.cipher.decrypt(credential["encrypted_password"].encode("ascii")).decode("utf-8")

    def delete_credential(self, user: dict, credential_id: int) -> None:
        if not self.repository.get_credential(credential_id, user["id"]):
            raise ValueError("Không tìm thấy tài khoản web.")
        self.repository.delete_credential(credential_id, user["id"])
        self.repository.add_audit_log(user["username"], "web_credential_deleted", f"Xóa tài khoản web #{credential_id}")
