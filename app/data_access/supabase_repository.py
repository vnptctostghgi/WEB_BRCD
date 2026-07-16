import sqlite3
import json
import re
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.data_access.app_repository import (
    DEFAULT_DASHBOARD_LAYOUT,
    DEFAULT_DASHBOARD_PAGE_ID,
    DEFAULT_DASHBOARD_PAGE_NAME,
    FEATURE_CODE_ALIASES,
    LEGACY_REMOVED_FEATURE_CODES,
    dashboard_feature_code_for_page,
    hash_password,
    normalize_feature_code,
)
from app.modules.mobile_gateway.migrations import MOBILE_GATEWAY_FEATURE_ROWS


FEATURE_ROWS = [
    {"code": "dashboard", "name": "Tổng quan", "parent_code": None, "sort_order": 10},
    {"code": "quantriweb", "name": "Quản trị hệ thống", "parent_code": None, "sort_order": 20},
    {"code": "quantringuoidung", "name": "Quản trị người dùng", "parent_code": "quantriweb", "sort_order": 21},
    {"code": "quantriketnoi", "name": "Quản trị kết nối", "parent_code": "quantriweb", "sort_order": 22},
    {"code": "phanquyennguoidung", "name": "Phân quyền người dùng", "parent_code": "quantriweb", "sort_order": 23},
    {"code": "phanquyendulieunguoidung", "name": "Phân quyền dữ liệu người dùng", "parent_code": "quantriweb", "sort_order": 24},
    {"code": "quantridanhmuc", "name": "Quản trị danh mục", "parent_code": "quantriweb", "sort_order": 25},
    {"code": "quantrivaitro", "name": "Quản trị vai trò", "parent_code": "quantridanhmuc", "sort_order": 26},
    {"code": "quantrimenu", "name": "Quản trị menu", "parent_code": "quantriweb", "sort_order": 27},
    {"code": "quanlycongviec", "name": "Quản lý công việc", "parent_code": None, "sort_order": 28},
    {"code": "truyvansql", "name": "Truy vấn SQL", "parent_code": None, "sort_order": 30},
    {"code": "baocaomoi", "name": "Báo cáo mới", "parent_code": None, "sort_order": 35},
    {"code": "thietkelayoutbaocao", "name": "Thiết kế Layout báo cáo", "parent_code": "baocaomoi", "sort_order": 36},
    {"code": "daodulieuonebss", "name": "Đào dữ liệu OneBSS", "parent_code": "baocaomoi", "sort_order": 37},
    {"code": "linkbaocao", "name": "Link báo cáo", "parent_code": "baocaomoi", "sort_order": 38},
    {"code": "taikhoanweb", "name": "Tài khoản web", "parent_code": "quantriweb", "sort_order": 40},
    {"code": "xemdanhsachtaikhoan", "name": "Xem danh sách tài khoản", "parent_code": "taikhoanweb", "sort_order": 41},
    {"code": "themvasuataikhoan", "name": "Thêm và sửa tài khoản", "parent_code": "taikhoanweb", "sort_order": 42},
    {"code": "xemmatkhaudaluu", "name": "Xem mật khẩu đã lưu", "parent_code": "taikhoanweb", "sort_order": 43},
    {"code": "nhatkyhoatdong", "name": "Nhật ký hoạt động", "parent_code": "quantriweb", "sort_order": 90},
]

ONEBSS_WORKER_META_KEY = "$worker"
ONEBSS_WORKER_COLUMNS = {
    "worker_id",
    "worker_session_id",
    "otp_request_id",
    "claimed_at",
    "updated_at",
}

FEATURE_ROWS.append({"code": "quantrisql", "name": "Quản trị SQL", "parent_code": "quantriketnoi", "sort_order": 23})
FEATURE_ROWS.append({"code": "quantridulieuonebss", "name": "Quản trị dữ liệu OneBSS", "parent_code": "quantriketnoi", "sort_order": 24})
FEATURE_ROWS.extend(
    {"code": code, "name": name, "parent_code": parent_code, "sort_order": sort_order}
    for code, name, parent_code, sort_order in MOBILE_GATEWAY_FEATURE_ROWS
)
OBSOLETE_FEATURE_CODES = (
    *LEGACY_REMOVED_FEATURE_CODES,
    *FEATURE_CODE_ALIASES.keys(),
)


REGION_ROWS = [
    {"code": "ALL", "name": "Tat ca", "is_active": True, "sort_order": 0},
    {"code": "13", "name": "Can Tho", "is_active": True, "sort_order": 10},
    {"code": "66", "name": "Hau Giang", "is_active": True, "sort_order": 20},
    {"code": "47", "name": "Soc Trang", "is_active": True, "sort_order": 30},
]

ROLE_ROWS = [
    {"code": "admin", "name": "Quan tri he thong", "description": "Toan quyen quan tri va cau hinh he thong.", "is_active": True, "sort_order": 10},
    {"code": "region_manager", "name": "Quan ly phan vung", "description": "Quan ly so lieu va nguoi dung theo phan vung duoc cap.", "is_active": True, "sort_order": 20},
    {"code": "data_entry", "name": "Nhan vien nhap lieu", "description": "Nhap va kiem tra du lieu nghiep vu.", "is_active": True, "sort_order": 30},
    {"code": "viewer", "name": "Nguoi xem", "description": "Xem bao cao va chuc nang duoc phan quyen.", "is_active": True, "sort_order": 40},
]


class SupabaseRepository:
    """Data Access Layer dung Supabase REST/PostgREST lam DB chinh."""

    def __init__(self, rest_url: str, secret_key: str) -> None:
        self.rest_url = rest_url.rstrip("/")
        self.secret_key = secret_key

    def initialize(self, admin_username: str, admin_password: str) -> None:
        self._migrate_feature_codes()
        for feature in FEATURE_ROWS:
            self._seed_feature(feature)
        self._patch_fixed_feature_labels()
        for region in REGION_ROWS:
            now = self._now()
            try:
                self._upsert("data_regions", {**region, "created_at": now, "updated_at": now}, "code")
            except RuntimeError:
                # Production can deploy before the operator runs the new SQL patch.
                # Feature routes will report the schema error until the patch is applied.
                pass
        for role in ROLE_ROWS:
            now = self._now()
            try:
                self._upsert("system_roles", {**role, "created_at": now, "updated_at": now}, "code")
            except RuntimeError:
                pass
        self._migrate_legacy_feature_layout()
        self._delete_obsolete_features()
        admin = self.get_user_by_username(admin_username)
        if not admin:
            user_id = self.create_user(admin_username, "Quan tri vien he thong", admin_password, "admin")
            admin = self.get_user_by_id(user_id)
        if admin:
            self.set_user_permissions(admin["id"], [feature["code"] for feature in FEATURE_ROWS])
        try:
            self._ensure_default_dashboard_layout()
        except RuntimeError:
            # Operator may deploy code before running the SQL patch for dashboard_layouts.
            pass

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        rows = self._get("users", {"username": f"eq.{username}"})
        return rows[0] if rows else None

    def _migrate_feature_codes(self) -> None:
        try:
            rows = self._get("features", {"select": "code,name,parent_code,sort_order"})
        except RuntimeError:
            return
        existing_codes = {str(row.get("code") or "") for row in rows}
        migrations: dict[str, str] = {}
        for row in rows:
            old_code = str(row.get("code") or "")
            if old_code in LEGACY_REMOVED_FEATURE_CODES:
                continue
            new_code = normalize_feature_code(old_code)
            if not new_code or new_code == old_code:
                continue
            migrations[old_code] = new_code
            if new_code not in existing_codes:
                try:
                    self._insert("features", {
                        "code": new_code,
                        "name": row.get("name") or new_code,
                        "parent_code": normalize_feature_code(row.get("parent_code")) or None,
                        "sort_order": int(row.get("sort_order") or 0),
                    })
                    existing_codes.add(new_code)
                except RuntimeError:
                    pass
            try:
                permissions = self._get("user_permissions", {
                    "feature_code": f"eq.{old_code}",
                    "select": "user_id",
                })
                if permissions:
                    self._post(
                        "user_permissions",
                        [{"user_id": int(permission["user_id"]), "feature_code": new_code} for permission in permissions],
                        {"Prefer": "resolution=ignore-duplicates,return=minimal"},
                    )
            except RuntimeError:
                pass

        for old_code, new_code in migrations.items():
            try:
                self._patch("features", {"parent_code": f"eq.{old_code}"}, {"parent_code": new_code})
            except RuntimeError:
                pass
        for old_code in migrations:
            try:
                self._delete("user_permissions", {"feature_code": f"eq.{old_code}"})
                self._delete("features", {"code": f"eq.{old_code}"})
            except RuntimeError:
                pass

    def _seed_feature(self, feature: dict[str, Any]) -> None:
        rows = self._get("features", {"code": f"eq.{feature['code']}", "select": "code", "limit": "1"})
        if rows:
            # Giữ nguyên name/parent_code/sort_order vì admin có thể đã sắp xếp menu trong giao diện.
            return
        self._insert("features", feature)

    def _patch_fixed_feature_labels(self) -> None:
        try:
            self._patch("features", {"code": "eq.truyvansql"}, {"name": "Truy vấn SQL"})
            self._patch("features", {"code": "eq.baocaomoi"}, {"name": "Báo cáo mới"})
            self._patch("features", {"code": "eq.quantriweb"}, {"name": "Quản trị hệ thống"})
            report_children = self._get("features", {"parent_code": "eq.truyvansql", "select": "code"})
            for child in report_children:
                payload = {"parent_code": "baocaomoi"}
                if child.get("code") == "thietkelayoutbaocao":
                    payload["sort_order"] = 36
                self._patch("features", {"code": f"eq.{child.get('code')}"}, payload)
        except RuntimeError:
            pass

    def _migrate_legacy_feature_layout(self) -> None:
        has_legacy = False
        for code in ("admin", "admin.connections.test", "admin.menu", "new_reports"):
            try:
                has_legacy = bool(self._get("features", {"code": f"eq.{code}", "select": "code", "limit": "1"})) or has_legacy
            except RuntimeError:
                return
        if not has_legacy:
            return
        for feature in FEATURE_ROWS:
            try:
                self._patch("features", {"code": f"eq.{feature['code']}"}, {
                    "name": feature["name"],
                    "parent_code": feature["parent_code"],
                    "sort_order": feature["sort_order"],
                })
            except RuntimeError:
                pass

    def _delete_obsolete_features(self) -> None:
        for code in OBSOLETE_FEATURE_CODES:
            try:
                self._delete("user_permissions", {"feature_code": f"eq.{code}"})
                self._delete("features", {"code": f"eq.{code}"})
            except RuntimeError:
                pass

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        rows = self._get("users", {"id": f"eq.{user_id}"})
        return rows[0] if rows else None

    def list_users(self) -> list[dict[str, Any]]:
        try:
            return self._get("users", {
                "select": "id,username,full_name,employee_code,email,phone,birth_date,gender,department,job_title,role,is_active,must_change_password,created_at,updated_at",
                "order": "id.asc",
            })
        except RuntimeError as error:
            if "employee_code" not in str(error):
                raise
            return self._get("users", {"select": "id,username,full_name,role,is_active,must_change_password,created_at,updated_at", "order": "id.asc"})

    def create_user(self, username: str, full_name: str, password: str, role: str, employee: dict[str, Any] | None = None) -> int:
        now = self._now()
        employee = employee or {}
        payload = {
            "username": username,
            "full_name": full_name,
            "employee_code": employee.get("employee_code"),
            "email": employee.get("email"),
            "phone": employee.get("phone"),
            "birth_date": employee.get("birth_date"),
            "gender": employee.get("gender"),
            "department": employee.get("department"),
            "job_title": employee.get("job_title"),
            "password_hash": hash_password(password),
            "role": role,
            "is_active": True,
            "must_change_password": True,
            "created_at": now,
            "updated_at": now,
        }
        try:
            row = self._insert("users", payload)
        except RuntimeError as error:
            if employee or "employee_code" not in str(error):
                raise
            row = self._insert("users", {
                "username": username,
                "full_name": full_name,
                "password_hash": hash_password(password),
                "role": role,
                "is_active": True,
                "must_change_password": True,
                "created_at": now,
                "updated_at": now,
            })
        return int(row["id"])

    def update_user(self, user_id: int, full_name: str, role: str, is_active: bool) -> None:
        self._patch("users", {"id": f"eq.{user_id}"}, {
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
            "updated_at": self._now(),
        })

    def delete_user(self, user_id: int) -> None:
        self._delete("users", {"id": f"eq.{user_id}"})

    def get_user_by_employee_or_email(self, employee_code: str, email: str) -> dict[str, Any] | None:
        try:
            rows = self._get("users", {"or": f"(employee_code.eq.{employee_code},email.eq.{email})"})
        except RuntimeError as error:
            if "employee_code" in str(error) or "email" in str(error):
                raise RuntimeError("Supabase chua co cot employee_code/email. Hay chay lai sql/supabase_schema.sql truoc khi import nguoi dung.") from error
            raise
        return rows[0] if rows else None

    def change_password(self, user_id: int, password: str, must_change: bool = False) -> None:
        self._patch("users", {"id": f"eq.{user_id}"}, {
            "password_hash": hash_password(password),
            "must_change_password": must_change,
            "updated_at": self._now(),
        })

    def count_active_admins(self) -> int:
        return len(self._get("users", {"role": "eq.admin", "is_active": "eq.true", "select": "id"}))

    def add_audit_log(self, actor: str, action: str, details: str) -> None:
        self._insert("audit_logs", {"actor": actor, "action": action, "details": details, "created_at": self._now()})

    def record_login_failure(self, username: str, ip_address: str) -> int:
        normalized = (username or "unknown").strip().lower() or "unknown"
        rows = self._get("login_attempts", {"username": f"eq.{normalized}", "select": "fail_count", "limit": "1"})
        fail_count = int(rows[0]["fail_count"]) + 1 if rows else 1
        now = self._now()
        self._upsert("login_attempts", {
            "username": normalized,
            "fail_count": fail_count,
            "last_ip": ip_address,
            "last_failed_at": now,
            "updated_at": now,
        }, "username")
        return fail_count

    def reset_login_failures(self, username: str) -> None:
        normalized = (username or "unknown").strip().lower() or "unknown"
        self._delete("login_attempts", {"username": f"eq.{normalized}"})

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

    def update_feature_layout(self, code: str, name: str, parent_code: str | None, sort_order: int) -> None:
        if parent_code == code:
            raise ValueError("Chức năng cha không được trùng chính nó.")
        self._patch("features", {"code": f"eq.{code}"}, {
            "name": name,
            "parent_code": parent_code or None,
            "sort_order": sort_order,
        })

    def create_menu_feature(self, name: str) -> dict[str, Any]:
        menu_name = name.strip()
        if not menu_name:
            raise ValueError("Tên menu không được để trống.")
        base_code = normalize_feature_code(menu_name) or "menu"
        rows = self._get("features", {"select": "code"})
        existing_codes = {str(row.get("code") or "") for row in rows}
        existing_normalized_codes = {normalize_feature_code(code) for code in existing_codes}
        code = base_code
        suffix = 2
        while code in existing_codes or normalize_feature_code(code) in existing_normalized_codes:
            code = f"{base_code}{suffix}"
            suffix += 1
        root_rows = self._get("features", {"parent_code": "is.null", "select": "sort_order"})
        max_order = max([int(row.get("sort_order") or 0) for row in root_rows] or [0])
        feature = self._insert("features", {
            "code": code,
            "name": menu_name,
            "parent_code": None,
            "sort_order": max_order + 10,
        })
        admin_users = self._get("users", {"role": "eq.admin", "select": "id"})
        if admin_users:
            self._post(
                "user_permissions",
                [{"user_id": int(user["id"]), "feature_code": code} for user in admin_users],
                {"Prefer": "resolution=ignore-duplicates,return=minimal"},
            )
        return feature

    def delete_feature(self, code: str) -> None:
        self._delete("user_permissions", {"feature_code": f"eq.{code}"})
        self._delete("features", {"code": f"eq.{code}"})

    def ensure_dashboard_layout_feature(self, page_id: str, page_name: str, parent_code: str | None = None) -> str:
        code = dashboard_feature_code_for_page(page_id)
        selected_parent = None
        if parent_code is not None:
            selected_parent = normalize_feature_code(parent_code) or "baocaomoi"
        existing = self._get("features", {"code": f"eq.{code}", "select": "code,parent_code", "limit": "1"})
        existing_code = existing[0]["code"] if existing else None
        existing_parent = existing[0].get("parent_code") if existing else None
        if not existing_code:
            for row in self._get("features", {"select": "code,parent_code"}):
                if normalize_feature_code(row.get("code")) == code:
                    existing_code = row["code"]
                    existing_parent = row.get("parent_code")
                    break
        if existing_code:
            if selected_parent is not None and selected_parent == existing_code:
                raise ValueError("Mục menu cha không được trùng với layout đang lưu.")
            if selected_parent is None:
                self._patch("features", {"code": f"eq.{existing_code}"}, {"name": page_name})
            elif selected_parent != existing_parent:
                siblings = self._get("features", {"parent_code": f"eq.{selected_parent}", "select": "sort_order"})
                max_order = max([int(row.get("sort_order") or 0) for row in siblings] or [0])
                self._patch("features", {"code": f"eq.{existing_code}"}, {
                    "name": page_name,
                    "parent_code": selected_parent,
                    "sort_order": max_order + 10,
                })
            else:
                self._patch("features", {"code": f"eq.{existing_code}"}, {"name": page_name, "parent_code": selected_parent})
            code = existing_code
        else:
            selected_parent = selected_parent or "baocaomoi"
            if selected_parent == code:
                raise ValueError("Mục menu cha không được trùng với layout đang lưu.")
            siblings = self._get("features", {"parent_code": f"eq.{selected_parent}", "select": "sort_order"})
            max_order = max([int(row.get("sort_order") or 0) for row in siblings] or [0])
            self._insert("features", {
                "code": code,
                "name": page_name,
                "parent_code": selected_parent,
                "sort_order": max_order + 10,
            })
        admin_users = self._get("users", {"role": "eq.admin", "select": "id"})
        if admin_users:
            self._post(
                "user_permissions",
                [{"user_id": int(user["id"]), "feature_code": code} for user in admin_users],
                {"Prefer": "resolution=ignore-duplicates,return=minimal"},
            )
        return code

    def get_user_permissions(self, user_id: int) -> list[str]:
        return [row["feature_code"] for row in self._get("user_permissions", {"user_id": f"eq.{user_id}", "select": "feature_code"})]

    def set_user_permissions(self, user_id: int, feature_codes: list[str]) -> None:
        self._delete("user_permissions", {"user_id": f"eq.{user_id}"})
        if feature_codes:
            self._post("user_permissions", [{"user_id": user_id, "feature_code": code} for code in feature_codes], {"Prefer": "return=minimal"})

    def set_bulk_user_permissions(self, user_ids: list[int], feature_codes: list[str]) -> None:
        for user_id in user_ids:
            self.set_user_permissions(user_id, feature_codes)

    def list_system_roles(self) -> list[dict[str, Any]]:
        return self._get("system_roles", {"order": "sort_order.asc"})

    def save_system_role(self, code: str, name: str, description: str, is_active: bool, sort_order: int) -> None:
        now = self._now()
        self._upsert("system_roles", {
            "code": code,
            "name": name,
            "description": description,
            "is_active": is_active,
            "sort_order": sort_order,
            "created_at": now,
            "updated_at": now,
        }, "code")

    def delete_system_role(self, code: str) -> None:
        self._delete("system_roles", {"code": f"eq.{code}"})

    def list_data_regions(self, active_only: bool = False) -> list[dict[str, Any]]:
        params = {"order": "sort_order.asc"}
        if active_only:
            params["is_active"] = "eq.true"
        return self._get("data_regions", params)

    def save_data_region(self, code: str, name: str, is_active: bool, sort_order: int) -> None:
        now = self._now()
        self._upsert("data_regions", {"code": code, "name": name, "is_active": is_active, "sort_order": sort_order, "created_at": now, "updated_at": now}, "code")

    def delete_data_region(self, code: str) -> None:
        self._delete("user_data_permissions", {"region_code": f"eq.{code}"})
        self._delete("data_regions", {"code": f"eq.{code}"})

    def get_user_data_permissions(self, user_id: int) -> list[str]:
        return [row["region_code"] for row in self._get("user_data_permissions", {"user_id": f"eq.{user_id}", "select": "region_code"})]

    def set_bulk_user_data_permissions(self, user_ids: list[int], region_codes: list[str]) -> None:
        for user_id in user_ids:
            self._delete("user_data_permissions", {"user_id": f"eq.{user_id}"})
            if region_codes:
                self._post("user_data_permissions", [{"user_id": user_id, "region_code": code} for code in region_codes], {"Prefer": "return=minimal"})

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

    def list_report_links(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        params = {"order": "ten_bao_cao.asc"}
        if not include_inactive:
            params["is_active"] = "eq.true"
        rows = self._get("report_links", params)
        return [self._decode_report_link(row) for row in rows]

    def get_report_link_by_id(self, report_id: int) -> dict[str, Any] | None:
        rows = self._get("report_links", {"id": f"eq.{report_id}", "limit": "1"})
        return self._decode_report_link(rows[0]) if rows else None

    def get_report_link_by_code(self, ma_bao_cao: str) -> dict[str, Any] | None:
        rows = self._get("report_links", {"ma_bao_cao": f"eq.{ma_bao_cao}", "limit": "1"})
        return self._decode_report_link(rows[0]) if rows else None

    def generate_report_link_code(self) -> str:
        rows = self._get("report_links", {"select": "ma_bao_cao", "ma_bao_cao": "like.LINK%", "order": "ma_bao_cao.desc"})
        numbers = []
        for row in rows:
            match = re.search(r"(\d+)$", str(row.get("ma_bao_cao") or ""))
            if match:
                numbers.append(int(match.group(1)))
        return f"LINK{(max(numbers) if numbers else 0) + 1:04d}"

    def save_report_link(
        self,
        report_id: int | None,
        ma_bao_cao: str,
        ten_bao_cao: str,
        link: str,
        link_type: str,
        is_active: bool,
    ) -> int:
        payload = {
            "ma_bao_cao": ma_bao_cao,
            "ten_bao_cao": ten_bao_cao,
            "link": link,
            "link_type": link_type,
            "is_active": is_active,
            "updated_at": self._now(),
        }
        if report_id:
            self._patch("report_links", {"id": f"eq.{report_id}"}, payload)
            return int(report_id)
        payload["created_at"] = self._now()
        return int(self._insert("report_links", payload)["id"])

    def delete_report_link(self, report_id: int) -> None:
        self._delete("report_links", {"id": f"eq.{report_id}"})

    def list_sql_reports(self) -> list[dict[str, Any]]:
        rows = self._get("sql_reports", {"order": "ten_bao_cao.asc"})
        return [self._decode_sql_report(row) for row in rows]

    def get_sql_report_by_id(self, report_id: int) -> dict[str, Any] | None:
        rows = self._get("sql_reports", {"id": f"eq.{report_id}"})
        return self._decode_sql_report(rows[0]) if rows else None

    def get_sql_report_by_code(self, ma_bao_cao: str) -> dict[str, Any] | None:
        rows = self._get("sql_reports", {"ma_bao_cao": f"eq.{ma_bao_cao}"})
        return self._decode_sql_report(rows[0]) if rows else None

    def save_sql_report(
        self,
        report_id: int | None,
        ten_bao_cao: str,
        ma_bao_cao: str,
        cau_lenh_sql: str,
        cac_tham_so: list[str],
    ) -> int:
        payload = {
            "ten_bao_cao": ten_bao_cao,
            "ma_bao_cao": ma_bao_cao,
            "cau_lenh_sql": cau_lenh_sql,
            "cac_tham_so": cac_tham_so,
            "updated_at": self._now(),
        }
        if report_id:
            self._patch("sql_reports", {"id": f"eq.{report_id}"}, payload)
            return int(report_id)
        payload["created_at"] = self._now()
        return int(self._insert("sql_reports", payload)["id"])

    def delete_sql_report(self, report_id: int) -> None:
        self._delete("sql_reports", {"id": f"eq.{report_id}"})

    def list_onebss_reports(self) -> list[dict[str, Any]]:
        rows = self._get("onebss_reports", {"order": "ten_bao_cao.asc"})
        return [self._decode_onebss_report(row) for row in rows]

    def get_onebss_report_by_id(self, report_id: int) -> dict[str, Any] | None:
        rows = self._get("onebss_reports", {"id": f"eq.{report_id}", "limit": "1"})
        return self._decode_onebss_report(rows[0]) if rows else None

    def get_onebss_report_by_code(self, ma_bao_cao: str) -> dict[str, Any] | None:
        rows = self._get("onebss_reports", {"ma_bao_cao": f"eq.{ma_bao_cao}", "limit": "1"})
        return self._decode_onebss_report(rows[0]) if rows else None

    def generate_onebss_report_code(self) -> str:
        rows = self._get("onebss_reports", {"select": "ma_bao_cao", "ma_bao_cao": "like.ONEBSS%", "order": "ma_bao_cao.desc"})
        numbers = []
        for row in rows:
            match = re.search(r"(\d+)$", str(row.get("ma_bao_cao") or ""))
            if match:
                numbers.append(int(match.group(1)))
        return f"ONEBSS{(max(numbers) if numbers else 0) + 1:04d}"

    def save_onebss_report(
        self,
        report_id: int | None,
        ma_bao_cao: str,
        ten_bao_cao: str,
        danh_sach_bien: list[str],
        parameters: dict[str, Any],
        report_url: str,
        storage_link: str,
        otp_service_code: str = "onebss",
    ) -> int:
        payload = {
            "ma_bao_cao": ma_bao_cao,
            "ten_bao_cao": ten_bao_cao,
            "danh_sach_bien": danh_sach_bien,
            "parameters": parameters if isinstance(parameters, dict) else {},
            "otp_service_code": str(otp_service_code or "onebss").strip().lower() or "onebss",
            "report_url": report_url,
            "storage_link": storage_link,
            "updated_at": self._now(),
        }
        legacy_payload = {key: value for key, value in payload.items() if key != "otp_service_code"}
        if report_id:
            try:
                self._patch("onebss_reports", {"id": f"eq.{report_id}"}, payload)
            except RuntimeError as error:
                if not self._is_missing_onebss_otp_service_column_error(error):
                    raise
                self._patch("onebss_reports", {"id": f"eq.{report_id}"}, legacy_payload)
            return int(report_id)
        payload["created_at"] = self._now()
        legacy_payload["created_at"] = payload["created_at"]
        try:
            return int(self._insert("onebss_reports", payload)["id"])
        except RuntimeError as error:
            if not self._is_missing_onebss_otp_service_column_error(error):
                raise
            return int(self._insert("onebss_reports", legacy_payload)["id"])

    def delete_onebss_report(self, report_id: int) -> None:
        self._delete("onebss_reports", {"id": f"eq.{report_id}"})

    def save_onebss_report_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id") or f"OBRUN{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}")
        row = {
            "run_id": run_id,
            "ma_bao_cao": str(payload.get("ma_bao_cao") or ""),
            "ten_bao_cao": str(payload.get("ten_bao_cao") or ""),
            "status": str(payload.get("status") or "failed"),
            "message": str(payload.get("message") or ""),
            "file_name": str(payload.get("file_name") or ""),
            "file_path": str(payload.get("file_path") or ""),
            "storage_link": str(payload.get("storage_link") or ""),
            "storage_status": str(payload.get("storage_status") or ""),
            "parameters_json": payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {},
            "started_at": str(payload.get("started_at") or self._now()),
            "finished_at": str(payload.get("finished_at") or self._now()),
            "duration_ms": int(payload.get("duration_ms") or 0),
            "created_by": str(payload.get("created_by") or ""),
            "worker_id": str(payload.get("worker_id") or ""),
            "worker_session_id": str(payload.get("worker_session_id") or ""),
            "otp_request_id": str(payload.get("otp_request_id") or ""),
            "claimed_at": str(payload.get("claimed_at") or ""),
            "updated_at": str(payload.get("updated_at") or self._now()),
        }
        try:
            self._insert("onebss_report_runs", row)
        except RuntimeError as error:
            if not self._is_missing_onebss_worker_column(error):
                raise
            legacy_row = self._onebss_legacy_run_payload(row)
            self._insert("onebss_report_runs", legacy_row)
            row = legacy_row
        return self._decode_onebss_report_run(row)

    def get_onebss_report_run(self, run_id: str) -> dict[str, Any] | None:
        rows = self._get("onebss_report_runs", {"run_id": f"eq.{run_id}", "limit": "1"})
        return self._decode_onebss_report_run(rows[0]) if rows else None

    def claim_next_onebss_report_run(self, worker_id: str) -> dict[str, Any] | None:
        rows = self._get("onebss_report_runs", {"status": "eq.queued", "order": "started_at.asc", "limit": "1"})
        if not rows:
            return None
        run_id = str(rows[0].get("run_id") or "")
        now = self._now()
        payload = {
            "status": "running",
            "message": "May tram da nhan task va dang xu ly OneBSS.",
            "worker_id": str(worker_id or "")[:120],
            "claimed_at": now,
            "updated_at": now,
        }
        try:
            self._patch("onebss_report_runs", {"run_id": f"eq.{run_id}", "status": "eq.queued"}, payload)
        except RuntimeError as error:
            if not self._is_missing_onebss_worker_column(error):
                raise
            current = self._decode_onebss_report_run(rows[0])
            legacy_payload = {
                "status": payload["status"],
                "message": payload["message"],
                "parameters_json": self._onebss_parameters_with_worker_meta(current.get("parameters"), payload),
            }
            self._patch("onebss_report_runs", {"run_id": f"eq.{run_id}", "status": "eq.queued"}, legacy_payload)
        return self.get_onebss_report_run(run_id)

    def update_onebss_report_run(self, run_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "status",
            "message",
            "file_name",
            "file_path",
            "storage_link",
            "storage_status",
            "parameters_json",
            "finished_at",
            "duration_ms",
            "worker_id",
            "worker_session_id",
            "otp_request_id",
            "claimed_at",
            "updated_at",
        }
        payload: dict[str, Any] = {}
        for key, value in updates.items():
            if key == "parameters" and isinstance(value, dict):
                payload["parameters_json"] = value
            elif key in allowed:
                payload[key] = value
        payload["updated_at"] = str(payload.get("updated_at") or self._now())
        if payload:
            try:
                self._patch("onebss_report_runs", {"run_id": f"eq.{run_id}"}, payload)
            except RuntimeError as error:
                if not self._is_missing_onebss_worker_column(error):
                    raise
                current = self.get_onebss_report_run(run_id) or {}
                legacy_payload = {key: value for key, value in payload.items() if key not in ONEBSS_WORKER_COLUMNS}
                parameters = legacy_payload.get("parameters_json")
                if not isinstance(parameters, dict):
                    parameters = current.get("parameters") if isinstance(current.get("parameters"), dict) else {}
                worker_meta = {
                    key: payload.get(key) or current.get(key) or ""
                    for key in ONEBSS_WORKER_COLUMNS
                }
                legacy_payload["parameters_json"] = self._onebss_parameters_with_worker_meta(parameters, worker_meta)
                self._patch("onebss_report_runs", {"run_id": f"eq.{run_id}"}, legacy_payload)
        return self.get_onebss_report_run(run_id)

    def list_onebss_report_runs(self, ma_bao_cao: str = "", limit: int = 50) -> list[dict[str, Any]]:
        params = {"order": "started_at.desc", "limit": str(min(max(int(limit or 50), 1), 200))}
        if ma_bao_cao:
            params["ma_bao_cao"] = f"eq.{ma_bao_cao}"
        rows = self._get("onebss_report_runs", params)
        return [self._decode_onebss_report_run(row) for row in rows]

    def clear_onebss_report_runs(self, ma_bao_cao: str = "") -> int:
        if ma_bao_cao:
            existing = self._get("onebss_report_runs", {"select": "run_id", "ma_bao_cao": f"eq.{ma_bao_cao}"})
            self._delete("onebss_report_runs", {"ma_bao_cao": f"eq.{ma_bao_cao}"})
        else:
            existing = self._get("onebss_report_runs", {"select": "run_id"})
            self._delete("onebss_report_runs", {"run_id": "not.is.null"})
        return len(existing)

    def list_dashboard_layouts(self) -> list[dict[str, Any]]:
        return self._get("dashboard_layouts", {
            "select": "page_id,page_name,created_at,updated_at",
            "order": "updated_at.desc,page_name.asc",
        })

    def get_dashboard_layout(self, page_id: str) -> dict[str, Any] | None:
        rows = self._get("dashboard_layouts", {"page_id": f"eq.{page_id}", "limit": "1"})
        return self._decode_dashboard_layout(rows[0]) if rows else None

    def save_dashboard_layout(self, page_id: str, page_name: str, layout: dict[str, Any], parent_code: str | None = None) -> str:
        now = self._now()
        existing = self.get_dashboard_layout(page_id)
        payload = {
            "page_id": page_id,
            "page_name": page_name,
            "layout_json": layout,
            "updated_at": now,
        }
        if existing:
            self._patch("dashboard_layouts", {"page_id": f"eq.{page_id}"}, payload)
            return self.ensure_dashboard_layout_feature(page_id, page_name, parent_code)
        payload["created_at"] = now
        self._insert("dashboard_layouts", payload)
        return self.ensure_dashboard_layout_feature(page_id, page_name, parent_code)

    def delete_dashboard_layout(self, page_id: str) -> None:
        self._delete("dashboard_layouts", {"page_id": f"eq.{page_id}"})
        self._delete("dashboard_chart_cache", {"page_id": f"eq.{page_id}"})

    def get_dashboard_chart_cache(self, chart_key: str) -> dict[str, Any] | None:
        rows = self._get("dashboard_chart_cache", {"chart_key": f"eq.{chart_key}", "limit": "1"})
        return self._decode_dashboard_chart_cache(rows[0]) if rows else None

    def get_dashboard_chart_cache_many(self, chart_keys: list[str]) -> list[dict[str, Any]]:
        keys = [str(key) for key in chart_keys if str(key)]
        if not keys:
            return []
        rows = self._get("dashboard_chart_cache", {
            "chart_key": self._in_filter(keys),
        })
        return [self._decode_dashboard_chart_cache(row) for row in rows]

    def upsert_dashboard_chart_cache(self, entry: dict[str, Any]) -> None:
        payload = {
            "chart_key": entry["chart_key"],
            "page_id": entry["page_id"],
            "tab_id": entry["tab_id"],
            "widget_key": entry["widget_key"],
            "report_id": entry.get("report_id"),
            "sql_code": entry["sql_code"],
            "report_code": entry.get("report_code"),
            "report_name": entry.get("report_name"),
            "widget_title": entry.get("widget_title"),
            "widget_type": entry.get("widget_type"),
            "filters": entry.get("filters") or {},
            "payload": entry.get("payload") or {},
            "status": entry.get("status") or "success",
            "error_message": entry.get("error_message"),
            "duration_ms": entry.get("duration_ms"),
            "row_count": entry.get("row_count") or 0,
            "refreshed_at": entry["refreshed_at"],
            "expires_at": entry.get("expires_at"),
            "updated_at": entry["updated_at"],
        }
        self._upsert("dashboard_chart_cache", payload, "chart_key")

    def list_dashboard_chart_cache_keys(self, page_id: str | None = None) -> list[str]:
        params = {"select": "chart_key"}
        if page_id:
            params["page_id"] = f"eq.{page_id}"
        rows = self._get("dashboard_chart_cache", params)
        return [str(row.get("chart_key") or "") for row in rows if row.get("chart_key")]

    def delete_dashboard_chart_cache(self, chart_key: str) -> None:
        self._delete("dashboard_chart_cache", {"chart_key": f"eq.{chart_key}"})

    def delete_dashboard_chart_cache_for_sql_report(self, report_id: int | None = None, report_codes: list[str] | None = None) -> int:
        if report_id:
            self._delete("dashboard_chart_cache", {"report_id": f"eq.{report_id}"})
        codes = sorted({str(code or "").strip().upper() for code in (report_codes or []) if str(code or "").strip()})
        for code in codes:
            self._delete("dashboard_chart_cache", {"report_code": f"eq.{code}"})
            self._delete("dashboard_chart_cache", {"sql_code": f"eq.{code}"})
        return 0

    def _ensure_default_dashboard_layout(self) -> None:
        rows = self._get("dashboard_layouts", {"page_id": f"eq.{DEFAULT_DASHBOARD_PAGE_ID}", "select": "page_id", "limit": "1"})
        if rows:
            return
        now = self._now()
        self._insert("dashboard_layouts", {
            "page_id": DEFAULT_DASHBOARD_PAGE_ID,
            "page_name": DEFAULT_DASHBOARD_PAGE_NAME,
            "layout_json": DEFAULT_DASHBOARD_LAYOUT,
            "created_at": now,
            "updated_at": now,
        })

    def list_work_tasks(self, include_completed: bool = False) -> list[dict[str, Any]]:
        params = {"order": "run_time.asc,task_id.asc"}
        if not include_completed:
            params.update({"is_active": "eq.true", "is_done": "eq.false"})
        rows = self._get("work_tasks", params)
        return [self._decode_work_task(row) for row in rows]

    def get_work_task(self, task_id: str) -> dict[str, Any] | None:
        rows = self._get("work_tasks", {"task_id": f"eq.{task_id}"})
        return self._decode_work_task(rows[0]) if rows else None

    def generate_work_task_id(self) -> str:
        rows = self._get("work_tasks", {"select": "task_id", "task_id": "like.TASK%", "order": "task_id.desc"})
        max_number = 0
        for row in rows:
            suffix = str(row.get("task_id", ""))[4:]
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"TASK{max_number + 1:04d}"

    def save_work_task(self, payload: dict[str, Any]) -> None:
        now = self._now()
        is_done = bool(payload.get("check", False))
        row = {
            "task_id": str(payload["task_id"]).strip(),
            "ten_cong_viec": str(payload.get("ten_cong_viec", "")).strip(),
            "schedule_type": str(payload.get("type", "Daily")).strip() or "Daily",
            "run_time": str(payload.get("time", "07:00")).strip() or "07:00",
            "weekday": str(payload.get("weekday", "")).strip(),
            "once_date": str(payload.get("once_date") or "").strip() or None,
            "group_name": str(payload.get("group", "")).strip(),
            "is_done": is_done,
            "is_active": False if is_done else bool(payload.get("is_active", True)),
            "created_at": now,
            "updated_at": now,
        }
        self._upsert("work_tasks", row, "task_id")

    def delete_work_task(self, task_id: str) -> None:
        self._delete("work_tasks", {"task_id": f"eq.{task_id}"})

    def complete_work_task(self, task_id: str) -> None:
        self._patch("work_tasks", {"task_id": f"eq.{task_id}"}, {
            "is_done": True,
            "is_active": False,
            "completed_at": self._now(),
            "updated_at": self._now(),
        })

    def mark_work_task_notified(self, task_id: str, notified_date: str) -> None:
        self._patch("work_tasks", {"task_id": f"eq.{task_id}"}, {
            "last_notified_date": notified_date,
            "last_notified_at": self._now(),
            "updated_at": self._now(),
        })

    def list_zalo_auto_messages(self, active_only: bool = False) -> list[dict[str, Any]]:
        params = {"order": "run_time.asc,schedule_id.asc"}
        if active_only:
            params["is_active"] = "eq.true"
        rows = self._get("zalo_auto_messages", params)
        return [self._decode_zalo_auto_message(row) for row in rows]

    def get_zalo_auto_message(self, schedule_id: str) -> dict[str, Any] | None:
        rows = self._get("zalo_auto_messages", {"schedule_id": f"eq.{schedule_id}", "limit": "1"})
        return self._decode_zalo_auto_message(rows[0]) if rows else None

    def generate_zalo_auto_message_id(self) -> str:
        rows = self._get("zalo_auto_messages", {"select": "schedule_id", "schedule_id": "like.ZALO%", "order": "schedule_id.desc"})
        max_number = 0
        for row in rows:
            suffix = str(row.get("schedule_id", ""))[4:]
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"ZALO{max_number + 1:04d}"

    def save_zalo_auto_message(self, payload: dict[str, Any]) -> None:
        now = self._now()
        row = {
            "schedule_id": str(payload["schedule_id"]).strip(),
            "name": str(payload.get("name", "")).strip(),
            "page_url": str(payload.get("page_url", "/")).strip() or "/",
            "page_label": str(payload.get("page_label", "")).strip(),
            "schedule_type": str(payload.get("schedule_type", "Daily")).strip() or "Daily",
            "time_slots": payload.get("time_slots") if isinstance(payload.get("time_slots"), list) else [],
            "run_time": str(payload.get("run_time", "07:00")).strip() or "07:00",
            "weekday": str(payload.get("weekday", "")).strip(),
            "month_day": int(payload.get("month_day") or 1),
            "target_type": str(payload.get("target_type", "group")).strip() or "group",
            "chat_id": str(payload.get("chat_id", "")).strip(),
            "chat_name": str(payload.get("chat_name", "")).strip(),
            "caption": str(payload.get("caption", "")).strip(),
            "photo_url": str(payload.get("photo_url", "")).strip(),
            "is_active": bool(payload.get("is_active", True)),
            "created_at": now,
            "updated_at": now,
        }
        self._upsert("zalo_auto_messages", row, "schedule_id")

    def delete_zalo_auto_message(self, schedule_id: str) -> None:
        self._delete("zalo_message_captures", {"schedule_id": f"eq.{schedule_id}"})
        self._delete("zalo_auto_messages", {"schedule_id": f"eq.{schedule_id}"})

    def mark_zalo_auto_message_run(self, schedule_id: str, run_key: str, ok: bool, error_message: str = "") -> None:
        now = self._now()
        payload = {
            "last_run_key": run_key,
            "last_error": str(error_message or "")[:500],
            "updated_at": now,
        }
        if ok:
            payload.update({"last_sent_key": run_key, "last_sent_at": now})
        self._patch("zalo_auto_messages", {"schedule_id": f"eq.{schedule_id}"}, payload)

    def save_zalo_message_capture(self, schedule_id: str, image_base64: str, mime_type: str, page_url: str = "", created_by: str = "") -> dict[str, Any]:
        now = self._now()
        row = {
            "capture_id": f"CAP{uuid.uuid4().hex[:16].upper()}",
            "schedule_id": schedule_id,
            "mime_type": mime_type or "image/png",
            "image_base64": image_base64,
            "public_token": secrets.token_urlsafe(24),
            "page_url": page_url or "",
            "created_by": created_by or "",
            "created_at": now,
        }
        self._insert("zalo_message_captures", row)
        return self._decode_zalo_capture(row, include_image=False)

    def get_latest_zalo_message_capture(self, schedule_id: str, include_image: bool = False) -> dict[str, Any] | None:
        select = "*" if include_image else "capture_id,schedule_id,mime_type,public_token,page_url,created_by,created_at"
        rows = self._get("zalo_message_captures", {
            "schedule_id": f"eq.{schedule_id}",
            "select": select,
            "order": "created_at.desc",
            "limit": "1",
        })
        return self._decode_zalo_capture(rows[0], include_image=include_image) if rows else None

    def get_zalo_message_capture(self, capture_id: str) -> dict[str, Any] | None:
        rows = self._get("zalo_message_captures", {"capture_id": f"eq.{capture_id}", "limit": "1"})
        return self._decode_zalo_capture(rows[0], include_image=True) if rows else None

    def list_data_mining_schedules(self, active_only: bool = False) -> list[dict[str, Any]]:
        params = {"order": "run_time.asc,schedule_id.asc"}
        if active_only:
            params["is_active"] = "eq.true"
        rows = self._get("data_mining_schedules", params)
        return [self._decode_data_mining_schedule(row) for row in rows]

    def get_data_mining_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        rows = self._get("data_mining_schedules", {"schedule_id": f"eq.{schedule_id}", "limit": "1"})
        return self._decode_data_mining_schedule(rows[0]) if rows else None

    def generate_data_mining_schedule_id(self) -> str:
        rows = self._get("data_mining_schedules", {"select": "schedule_id", "schedule_id": "like.MINE%", "order": "schedule_id.desc"})
        max_number = 0
        for row in rows:
            suffix = str(row.get("schedule_id", ""))[4:]
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"MINE{max_number + 1:04d}"

    def save_data_mining_schedule(self, payload: dict[str, Any]) -> None:
        now = self._now()
        row = {
            "schedule_id": str(payload["schedule_id"]).strip(),
            "name": str(payload.get("name", "")).strip(),
            "report_url": str(payload.get("report_url", "")).strip(),
            "schedule_type": str(payload.get("schedule_type", "Daily")).strip() or "Daily",
            "run_time": str(payload.get("run_time", "07:00")).strip() or "07:00",
            "weekday": str(payload.get("weekday", "")).strip(),
            "month_day": int(payload.get("month_day") or 1),
            "storage_link": str(payload.get("storage_link", "")).strip(),
            "file_name_template": str(payload.get("file_name_template", "")).strip(),
            "parameters": payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {},
            "is_active": bool(payload.get("is_active", True)),
            "created_at": now,
            "updated_at": now,
        }
        self._upsert("data_mining_schedules", row, "schedule_id")

    def delete_data_mining_schedule(self, schedule_id: str) -> None:
        self._delete("data_mining_runs", {"schedule_id": f"eq.{schedule_id}"})
        self._delete("data_mining_schedules", {"schedule_id": f"eq.{schedule_id}"})

    def create_data_mining_run(
        self,
        schedule_id: str,
        parameters: dict[str, Any] | None = None,
        created_by: str = "",
        status: str = "running",
        message: str = "",
    ) -> dict[str, Any]:
        now = self._now()
        row = {
            "run_id": f"RUN{uuid.uuid4().hex[:16].upper()}",
            "schedule_id": schedule_id,
            "status": str(status or "running")[:50],
            "message": str(message or "")[:1000],
            "file_name": "",
            "file_path": "",
            "storage_link": "",
            "storage_status": "",
            "parameters": parameters if isinstance(parameters, dict) else {},
            "started_at": now,
            "finished_at": None,
            "duration_ms": 0,
            "created_by": created_by or "",
        }
        self._insert("data_mining_runs", row)
        return self._decode_data_mining_run(row)

    def finish_data_mining_run(self, run_id: str, result: dict[str, Any]) -> None:
        payload = {
            "status": str(result.get("status") or ("success" if result.get("ok") else "failed"))[:50],
            "message": str(result.get("message") or "")[:1000],
            "file_name": str(result.get("file_name") or "")[:255],
            "file_path": str(result.get("file_path") or "")[:1000],
            "storage_link": str(result.get("storage_link") or "")[:1000],
            "storage_status": str(result.get("storage_status") or "")[:255],
            "finished_at": self._now(),
            "duration_ms": int(result.get("duration_ms") or 0),
        }
        self._patch("data_mining_runs", {"run_id": f"eq.{run_id}"}, payload)

    def mark_data_mining_schedule_run(self, schedule_id: str, run_key: str, ok: bool, result: dict[str, Any]) -> None:
        now = self._now()
        payload = {
            "last_run_key": run_key,
            "last_run_at": now,
            "last_status": ("success" if ok else str(result.get("status") or "failed"))[:50],
            "last_error": "" if ok else str(result.get("message") or result.get("error") or "")[:500],
            "updated_at": now,
        }
        if ok:
            payload.update({
                "last_success_key": run_key,
                "last_success_at": now,
                "last_file_name": str(result.get("file_name") or "")[:255],
                "last_file_path": str(result.get("file_path") or "")[:1000],
            })
        self._patch("data_mining_schedules", {"schedule_id": f"eq.{schedule_id}"}, payload)

    def list_data_mining_runs(self, schedule_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
        params = {"order": "started_at.desc", "limit": str(min(max(int(limit or 50), 1), 200))}
        if schedule_id:
            params["schedule_id"] = f"eq.{schedule_id}"
        rows = self._get("data_mining_runs", params)
        return [self._decode_data_mining_run(row) for row in rows]

    def health_check(self) -> dict[str, Any]:
        rows = self._get("features", {"select": "code", "limit": "1"})
        return {"ok": True, "backend": "supabase", "feature_rows_seen": len(rows)}

    @staticmethod
    def _decode_connection(row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = row.get("config") or {}
        return row

    @staticmethod
    def _decode_report_link(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "ma_bao_cao": row.get("ma_bao_cao") or "",
            "ten_bao_cao": row.get("ten_bao_cao") or "",
            "link": row.get("link") or "",
            "link_type": row.get("link_type") or "other",
            "is_active": bool(row.get("is_active")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _decode_sql_report(row: dict[str, Any]) -> dict[str, Any]:
        params = row.get("cac_tham_so") or []
        row["cac_tham_so"] = params if isinstance(params, list) else []
        return row

    @staticmethod
    def _decode_dashboard_layout(row: dict[str, Any]) -> dict[str, Any]:
        layout = row.get("layout_json") or {}
        if isinstance(layout, str):
            try:
                layout = json.loads(layout)
            except json.JSONDecodeError:
                layout = {}
        row.pop("layout_json", None)
        row["layout"] = layout if isinstance(layout, dict) else {}
        return row

    @staticmethod
    def _decode_dashboard_chart_cache(row: dict[str, Any]) -> dict[str, Any]:
        row["filters"] = row.get("filters") if isinstance(row.get("filters"), dict) else {}
        row["payload"] = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        return row

    @staticmethod
    def _decode_work_task(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": row.get("task_id"),
            "ten_cong_viec": row.get("ten_cong_viec"),
            "type": row.get("schedule_type"),
            "time": row.get("run_time"),
            "weekday": row.get("weekday") or "",
            "once_date": row.get("once_date") or "",
            "group": row.get("group_name") or "",
            "check": bool(row.get("is_done")),
            "is_active": bool(row.get("is_active")),
            "last_notified_date": row.get("last_notified_date") or "",
            "last_notified_at": row.get("last_notified_at") or "",
            "completed_at": row.get("completed_at") or "",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _decode_zalo_auto_message(row: dict[str, Any]) -> dict[str, Any]:
        time_slots = row.get("time_slots") or []
        if isinstance(time_slots, str):
            try:
                time_slots = json.loads(time_slots)
            except json.JSONDecodeError:
                time_slots = []
        return {
            "schedule_id": row.get("schedule_id"),
            "name": row.get("name") or "",
            "page_url": row.get("page_url") or "/",
            "page_label": row.get("page_label") or "",
            "schedule_type": row.get("schedule_type") or "Daily",
            "time_slots": time_slots if isinstance(time_slots, list) else [],
            "run_time": row.get("run_time") or "07:00",
            "weekday": row.get("weekday") or "",
            "month_day": int(row.get("month_day") or 1),
            "target_type": row.get("target_type") or "group",
            "chat_id": row.get("chat_id") or "",
            "chat_name": row.get("chat_name") or "",
            "caption": row.get("caption") or "",
            "photo_url": row.get("photo_url") or "",
            "is_active": bool(row.get("is_active")),
            "last_run_key": row.get("last_run_key") or "",
            "last_sent_key": row.get("last_sent_key") or "",
            "last_sent_at": row.get("last_sent_at") or "",
            "last_error": row.get("last_error") or "",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _decode_zalo_capture(row: dict[str, Any], include_image: bool = False) -> dict[str, Any]:
        payload = {
            "capture_id": row.get("capture_id"),
            "schedule_id": row.get("schedule_id"),
            "mime_type": row.get("mime_type") or "image/png",
            "public_token": row.get("public_token") or "",
            "page_url": row.get("page_url") or "",
            "created_by": row.get("created_by") or "",
            "created_at": row.get("created_at"),
        }
        if include_image:
            payload["image_base64"] = row.get("image_base64") or ""
        return payload

    @staticmethod
    def _decode_onebss_report(row: dict[str, Any]) -> dict[str, Any]:
        variables = row.get("danh_sach_bien") or []
        if isinstance(variables, str):
            try:
                variables = json.loads(variables)
            except json.JSONDecodeError:
                variables = []
        parameters = row.get("parameters") or {}
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {}
        return {
            "id": row.get("id"),
            "ma_bao_cao": row.get("ma_bao_cao") or "",
            "ten_bao_cao": row.get("ten_bao_cao") or "",
            "danh_sach_bien": variables if isinstance(variables, list) else [],
            "parameters": parameters if isinstance(parameters, dict) else {},
            "otp_service_code": row.get("otp_service_code") or "onebss",
            "report_url": row.get("report_url") or "",
            "storage_link": row.get("storage_link") or "",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _decode_onebss_report_run(row: dict[str, Any]) -> dict[str, Any]:
        parameters = row.get("parameters_json") or row.get("parameters") or {}
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {}
        if not isinstance(parameters, dict):
            parameters = {}
        public_parameters = dict(parameters)
        worker_meta = public_parameters.pop(ONEBSS_WORKER_META_KEY, {})
        if not isinstance(worker_meta, dict):
            worker_meta = {}
        return {
            "run_id": row.get("run_id"),
            "ma_bao_cao": row.get("ma_bao_cao") or "",
            "ten_bao_cao": row.get("ten_bao_cao") or "",
            "status": row.get("status") or "",
            "message": row.get("message") or "",
            "file_name": row.get("file_name") or "",
            "file_path": row.get("file_path") or "",
            "storage_link": row.get("storage_link") or "",
            "storage_status": row.get("storage_status") or "",
            "parameters": public_parameters,
            "started_at": row.get("started_at") or "",
            "finished_at": row.get("finished_at") or "",
            "duration_ms": int(row.get("duration_ms") or 0),
            "created_by": row.get("created_by") or "",
            "worker_id": row.get("worker_id") or worker_meta.get("worker_id") or "",
            "worker_session_id": row.get("worker_session_id") or worker_meta.get("worker_session_id") or "",
            "otp_request_id": row.get("otp_request_id") or worker_meta.get("otp_request_id") or "",
            "claimed_at": row.get("claimed_at") or worker_meta.get("claimed_at") or "",
            "updated_at": row.get("updated_at") or worker_meta.get("updated_at") or "",
        }

    @staticmethod
    def _is_missing_onebss_worker_column(error: Exception) -> bool:
        text = str(error)
        return (
            "PGRST204" in text
            and "onebss_report_runs" in text
            and any(column in text for column in ONEBSS_WORKER_COLUMNS)
        )

    @staticmethod
    def _onebss_parameters_with_worker_meta(parameters: Any, worker_values: dict[str, Any]) -> dict[str, Any]:
        base = dict(parameters) if isinstance(parameters, dict) else {}
        meta = base.get(ONEBSS_WORKER_META_KEY) if isinstance(base.get(ONEBSS_WORKER_META_KEY), dict) else {}
        merged_meta = {
            **meta,
            **{
                key: str(worker_values.get(key) or "")
                for key in ONEBSS_WORKER_COLUMNS
                if worker_values.get(key)
            },
        }
        if merged_meta:
            base[ONEBSS_WORKER_META_KEY] = merged_meta
        else:
            base.pop(ONEBSS_WORKER_META_KEY, None)
        return base

    @classmethod
    def _onebss_legacy_run_payload(cls, row: dict[str, Any]) -> dict[str, Any]:
        legacy = {key: value for key, value in row.items() if key not in ONEBSS_WORKER_COLUMNS}
        legacy["parameters_json"] = cls._onebss_parameters_with_worker_meta(row.get("parameters_json"), row)
        return legacy

    @staticmethod
    def _decode_data_mining_schedule(row: dict[str, Any]) -> dict[str, Any]:
        parameters = row.get("parameters") or {}
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {}
        return {
            "schedule_id": row.get("schedule_id"),
            "name": row.get("name") or "",
            "report_url": row.get("report_url") or "",
            "schedule_type": row.get("schedule_type") or "Daily",
            "run_time": row.get("run_time") or "07:00",
            "weekday": row.get("weekday") or "",
            "month_day": int(row.get("month_day") or 1),
            "storage_link": row.get("storage_link") or "",
            "file_name_template": row.get("file_name_template") or "",
            "parameters": parameters if isinstance(parameters, dict) else {},
            "is_active": bool(row.get("is_active")),
            "last_run_key": row.get("last_run_key") or "",
            "last_success_key": row.get("last_success_key") or "",
            "last_run_at": row.get("last_run_at") or "",
            "last_success_at": row.get("last_success_at") or "",
            "last_status": row.get("last_status") or "",
            "last_error": row.get("last_error") or "",
            "last_file_name": row.get("last_file_name") or "",
            "last_file_path": row.get("last_file_path") or "",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _decode_data_mining_run(row: dict[str, Any]) -> dict[str, Any]:
        parameters = row.get("parameters") or {}
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {}
        return {
            "run_id": row.get("run_id"),
            "schedule_id": row.get("schedule_id"),
            "status": row.get("status") or "",
            "message": row.get("message") or "",
            "file_name": row.get("file_name") or "",
            "file_path": row.get("file_path") or "",
            "storage_link": row.get("storage_link") or "",
            "storage_status": row.get("storage_status") or "",
            "parameters": parameters if isinstance(parameters, dict) else {},
            "started_at": row.get("started_at") or "",
            "finished_at": row.get("finished_at") or "",
            "duration_ms": int(row.get("duration_ms") or 0),
            "created_by": row.get("created_by") or "",
        }

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"apikey": self.secret_key, "Content-Type": "application/json"}
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _is_missing_onebss_otp_service_column_error(error: Exception) -> bool:
        text = str(error)
        return "PGRST204" in text and "otp_service_code" in text and "onebss_reports" in text

    def _request(self, method: str, table: str, *, params: dict[str, str] | None = None, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        url = f"{self.rest_url}/{table}"
        with httpx.Client(timeout=20) as client:
            response = client.request(method, url, params=params, json=json, headers=self._headers(headers))
        if response.status_code == 409:
            raise sqlite3.IntegrityError(response.text)
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase REST loi {response.status_code}: {response.text[:300]}")
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
    def _in_filter(values: list[str]) -> str:
        escaped_values = [
            '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
            for value in values
        ]
        return f"in.({','.join(escaped_values)})"

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")
