import sqlite3
from typing import Any

from app.data_access.app_repository import AppRepository, verify_password


class AuthService:
    def __init__(self, repository: AppRepository) -> None:
        self.repository = repository

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        user = self.repository.get_user_by_username(username.strip())
        if not user or not user["is_active"] or not verify_password(password, user["password_hash"]):
            self.repository.add_audit_log(username.strip() or "unknown", "login_failed", "Đăng nhập thất bại")
            return None
        self.repository.add_audit_log(user["username"], "login_success", "Đăng nhập thành công")
        return self.public_user(user)

    def create_user(self, actor: str, username: str, full_name: str, password: str, role: str) -> dict[str, Any]:
        self._validate_user_input(username, full_name, password, role)
        try:
            user_id = self.repository.create_user(username.strip(), full_name.strip(), password, role)
        except sqlite3.IntegrityError as error:
            raise ValueError("Tên đăng nhập đã tồn tại.") from error
        self.repository.add_audit_log(actor, "user_created", f"Tạo người dùng {username.strip()} ({role})")
        return self.public_user(self.repository.get_user_by_id(user_id))

    def update_user(self, actor: str, actor_id: int, user_id: int, full_name: str, role: str, is_active: bool) -> dict[str, Any]:
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        if role not in {"admin", "viewer"} or not full_name.strip():
            raise ValueError("Thông tin người dùng không hợp lệ.")
        removes_active_admin = user["role"] == "admin" and user["is_active"] and (role != "admin" or not is_active)
        if removes_active_admin and self.repository.count_active_admins() <= 1:
            raise ValueError("Hệ thống phải luôn có ít nhất một quản trị viên hoạt động.")
        if user_id == actor_id and not is_active:
            raise ValueError("Bạn không thể tự khóa tài khoản đang đăng nhập.")
        self.repository.update_user(user_id, full_name.strip(), role, is_active)
        self.repository.add_audit_log(actor, "user_updated", f"Cập nhật người dùng {user['username']}")
        return self.public_user(self.repository.get_user_by_id(user_id))

    def reset_password(self, actor: str, user_id: int, password: str) -> None:
        if len(password) < 10:
            raise ValueError("Mật khẩu phải có ít nhất 10 ký tự.")
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        self.repository.change_password(user_id, password, must_change=True)
        self.repository.add_audit_log(actor, "password_reset", f"Đặt lại mật khẩu cho {user['username']}")

    def change_own_password(self, user_id: int, username: str, current_password: str, new_password: str) -> None:
        user = self.repository.get_user_by_id(user_id)
        if not user or not verify_password(current_password, user["password_hash"]):
            raise ValueError("Mật khẩu hiện tại không đúng.")
        if len(new_password) < 10:
            raise ValueError("Mật khẩu mới phải có ít nhất 10 ký tự.")
        self.repository.change_password(user_id, new_password)
        self.repository.add_audit_log(username, "password_changed", "Đổi mật khẩu cá nhân")

    @staticmethod
    def public_user(user: dict[str, Any] | None) -> dict[str, Any]:
        if not user:
            return {}
        return {key: user[key] for key in ("id", "username", "full_name", "role", "is_active", "must_change_password")}

    @staticmethod
    def _validate_user_input(username: str, full_name: str, password: str, role: str) -> None:
        if len(username.strip()) < 3 or not username.strip().replace("_", "").isalnum():
            raise ValueError("Tên đăng nhập phải có ít nhất 3 ký tự, chỉ gồm chữ, số hoặc dấu gạch dưới.")
        if not full_name.strip():
            raise ValueError("Họ tên không được để trống.")
        if len(password) < 10:
            raise ValueError("Mật khẩu phải có ít nhất 10 ký tự.")
        if role not in {"admin", "viewer"}:
            raise ValueError("Vai trò không hợp lệ.")
