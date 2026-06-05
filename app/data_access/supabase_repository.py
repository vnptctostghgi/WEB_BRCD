import sqlite3
from datetime import UTC, datetime
from typing import Any

import httpx

from app.data_access.app_repository import hash_password


FEATURE_ROWS = [
    {"code": "dashboard", "name": "Tổng quan", "parent_code": None, "sort_order": 10},
    {"code": "vault", "name": "Kho tài khoản web", "parent_code": None, "sort_order": 20},
    {"code": "vault.view", "name": "Xem danh sách tài khoản", "parent_code": "vault", "sort_order": 21},
    {"code": "vault.manage", "name": "Thêm và sửa tài khoản", "parent_code": "vault", "sort_order": 22},
    {"code": "vault.reveal", "name": "Xem mật khẩu đã lưu", "parent_code": "vault", "sort_order": 23},
    {"code": "admin", "name": "Quản trị", "parent_code": None, "sort_order": 30},
    {"code": "admin.users", "name": "Quản trị người dùng", "parent_code": "admin", "sort_order": 31},
    {"code": "admin.catalogs", "name": "Quản trị danh mục website", "parent_code": "admin", "sort_order": 32},
    {"code": "admin.permissions", "name": "Phân quyền chức năng", "parent_code": "admin", "sort_order": 33},
    {"code": "admin.audit", "name": "Xem nhật ký hoạt động", "parent_code": "admin", "sort_order": 34},
    {"code": "admin.connections", "name": "Quản trị kết nối hệ thống", "parent_code": "admin", "sort_order": 35},
    {"code": "admin.connections.test", "name": "Kiểm tra kết nối hệ thống", "parent_code": "admin.connections", "sort_order": 36},
]


class SupabaseRepository:
    """Data Access Layer dùng Supabase REST/PostgREST làm DB chính."""

    def __init__(self, rest_url: str, secret_key: str) -> None:
        self.rest_url = rest_url.rstrip("/")
        self.secret_key = secret_key

    def initialize(self, admin_username: str, admin_password: str) -> None:
        for feature in FEATURE_ROWS:
            self._upsert("features", feature, "code")
        admin = self.get_user_by_username(admin_username)
        if not admin:
            user_id = self.create_user(admin_username, "Quản trị viên hệ thống", admin_password, "admin")
            admin = self.get_user_by_id(user_id)
        if admin:
            self.set_user_permissions(admin["id"], [feature["code"] for feature in FEATURE_ROWS])

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        rows = self._get("users", {"username": f"eq.{username}"})
        return rows[0] if rows else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        rows = self._get("users", {"id": f"eq.{user_id}"})
        return rows[0] if rows else None

    def list_users(self) -> list[dict[str, Any]]:
        return self._get("users", {"select": "id,username,full_name,role,is_active,must_change_password,created_at,updated_at", "order": "id.asc"})

    def create_user(self, username: str, full_name: str, password: str, role: str) -> int:
        now = self._now()
        row = self._insert("users", {
            "username": username, "full_name": full_name, "password_hash": hash_password(password),
            "role": role, "is_active": True, "must_change_password": True, "created_at": now, "updated_at": now,
        })
        return int(row["id"])

    def update_user(self, user_id: int, full_name: str, role: str, is_active: bool) -> None:
        self._patch("users", {"id": f"eq.{user_id}"}, {"full_name": full_name, "role": role, "is_active": is_active, "updated_at": self._now()})

    def change_password(self, user_id: int, password: str, must_change: bool = False) -> None:
        self._patch("users", {"id": f"eq.{user_id}"}, {"password_hash": hash_password(password), "must_change_password": must_change, "updated_at": self._now()})

    def count_active_admins(self) -> int:
        return len(self._get("users", {"role": "eq.admin", "is_active": "eq.true", "select": "id"}))

    def add_audit_log(self, actor: str, action: str, details: str) -> None:
        self._insert("audit_logs", {"actor": actor, "action": action, "details": details, "created_at": self._now()})

    def list_audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._get("audit_logs", {"order": "id.desc", "limit": str(limit)})

    def list_websites(self, active_only: bool = False) -> list[dict[str, Any]]:
        params = {"order": "name.asc"}
        if active_only:
            params["is_active"] = "eq.true"
        return self._get("website_catalog", params)

    def get_website(self, website_id: int) -> dict[str, Any] | None:
        rows = self._get("website_catalog", {"id": f"eq.{website_id}"})
        return rows[0] if rows else None

    def save_website(self, website_id: int | None, name: str, url: str, requires_otp: bool, is_active: bool) -> int:
        payload = {"name": name, "url": url, "requires_otp": requires_otp, "is_active": is_active, "updated_at": self._now()}
        if website_id:
            self._patch("website_catalog", {"id": f"eq.{website_id}"}, payload)
            return website_id
        payload["created_at"] = self._now()
        return int(self._insert("website_catalog", payload)["id"])

    def list_credentials(self, user_id: int) -> list[dict[str, Any]]:
        rows = self._get("web_credentials", {
            "user_id": f"eq.{user_id}",
            "select": "id,website_id,login_username,notes,created_at,updated_at,website_catalog(name,url,requires_otp)",
            "order": "login_username.asc",
        })
        for row in rows:
            website = row.pop("website_catalog") or {}
            row["website_name"] = website.get("name")
            row["url"] = website.get("url")
            row["requires_otp"] = website.get("requires_otp")
        return rows

    def get_credential(self, credential_id: int, user_id: int) -> dict[str, Any] | None:
        rows = self._get("web_credentials", {"id": f"eq.{credential_id}", "user_id": f"eq.{user_id}"})
        return rows[0] if rows else None

    def save_credential(self, credential_id: int | None, user_id: int, website_id: int, username: str, encrypted_password: str, notes: str) -> int:
        payload = {"website_id": website_id, "login_username": username, "encrypted_password": encrypted_password, "notes": notes, "updated_at": self._now()}
        if credential_id:
            self._patch("web_credentials", {"id": f"eq.{credential_id}", "user_id": f"eq.{user_id}"}, payload)
            return credential_id
        payload.update({"user_id": user_id, "created_at": self._now()})
        return int(self._insert("web_credentials", payload)["id"])

    def delete_credential(self, credential_id: int, user_id: int) -> None:
        self._delete("web_credentials", {"id": f"eq.{credential_id}", "user_id": f"eq.{user_id}"})

    def list_features(self) -> list[dict[str, Any]]:
        return self._get("features", {"order": "sort_order.asc"})

    def get_user_permissions(self, user_id: int) -> list[str]:
        return [row["feature_code"] for row in self._get("user_permissions", {"user_id": f"eq.{user_id}", "select": "feature_code"})]

    def set_user_permissions(self, user_id: int, feature_codes: list[str]) -> None:
        self._delete("user_permissions", {"user_id": f"eq.{user_id}"})
        if feature_codes:
            self._post("user_permissions", [{"user_id": user_id, "feature_code": code} for code in feature_codes], {"Prefer": "return=minimal"})

    def list_system_connections(self) -> list[dict[str, Any]]:
        rows = self._get("system_connections", {"order": "id.asc"})
        return [self._decode_connection(row) for row in rows]

    def get_system_connection_by_code(self, code: str) -> dict[str, Any] | None:
        rows = self._get("system_connections", {"code": f"eq.{code}"})
        return self._decode_connection(rows[0]) if rows else None

    def upsert_system_connection(self, code: str, name: str, connection_type: str, description: str, config: dict[str, Any], is_active: bool) -> int:
        existing = self.get_system_connection_by_code(code)
        payload = {
            "code": code,
            "name": name,
            "connection_type": connection_type,
            "description": description,
            "config": config,
            "is_active": is_active,
            "updated_at": self._now(),
        }
        if existing:
            self._patch("system_connections", {"code": f"eq.{code}"}, payload)
            return int(existing["id"])
        payload["created_at"] = self._now()
        return int(self._insert("system_connections", payload)["id"])

    def health_check(self) -> dict[str, Any]:
        rows = self._get("features", {"select": "code", "limit": "1"})
        return {"ok": True, "backend": "supabase", "feature_rows_seen": len(rows)}

    @staticmethod
    def _decode_connection(row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = row.get("config") or {}
        return row

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"apikey": self.secret_key, "Content-Type": "application/json"}
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method: str, table: str, *, params: dict[str, str] | None = None, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        url = f"{self.rest_url}/{table}"
        with httpx.Client(timeout=20) as client:
            response = client.request(method, url, params=params, json=json, headers=self._headers(headers))
        if response.status_code == 409:
            raise sqlite3.IntegrityError(response.text)
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase REST lỗi {response.status_code}: {response.text[:300]}")
        if response.text:
            return response.json()
        return None

    def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        return self._request("GET", table, params=params) or []

    def _insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = self._post(table, payload, {"Prefer": "return=representation"})
        except sqlite3.IntegrityError as exc:
            if "duplicate key value violates unique constraint" not in str(exc) or "id" in payload:
                raise
            next_id = self._next_id(table)
            rows = self._post(table, {**payload, "id": next_id}, {"Prefer": "return=representation"})
        return rows[0]

    def _post(self, table: str, payload: Any, headers: dict[str, str]) -> Any:
        return self._request("POST", table, json=payload, headers=headers)

    def _patch(self, table: str, params: dict[str, str], payload: dict[str, Any]) -> None:
        self._request("PATCH", table, params=params, json=payload, headers={"Prefer": "return=minimal"})

    def _delete(self, table: str, params: dict[str, str]) -> None:
        self._request("DELETE", table, params=params, headers={"Prefer": "return=minimal"})

    def _upsert(self, table: str, payload: dict[str, Any], conflict_column: str) -> None:
        self._request("POST", table, params={"on_conflict": conflict_column}, json=payload, headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def _next_id(self, table: str) -> int:
        rows = self._get(table, {"select": "id", "order": "id.desc", "limit": "1"})
        return int(rows[0]["id"]) + 1 if rows else 1

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")
