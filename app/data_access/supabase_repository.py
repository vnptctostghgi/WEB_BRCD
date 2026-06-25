import sqlite3
import json
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


FEATURE_ROWS = [
    {"code": "dashboard", "name": "Tổng quan", "parent_code": None, "sort_order": 10},
    {"code": "quantriweb", "name": "Quản trị web", "parent_code": None, "sort_order": 20},
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
    {"code": "taikhoanweb", "name": "Tài khoản web", "parent_code": "quantriweb", "sort_order": 40},
    {"code": "xemdanhsachtaikhoan", "name": "Xem danh sách tài khoản", "parent_code": "taikhoanweb", "sort_order": 41},
    {"code": "themvasuataikhoan", "name": "Thêm và sửa tài khoản", "parent_code": "taikhoanweb", "sort_order": 42},
    {"code": "xemmatkhaudaluu", "name": "Xem mật khẩu đã lưu", "parent_code": "taikhoanweb", "sort_order": 43},
    {"code": "nhatkyhoatdong", "name": "Nhật ký hoạt động", "parent_code": "quantriweb", "sort_order": 90},
]

FEATURE_ROWS.append({"code": "quantrisql", "name": "Quản trị SQL", "parent_code": "quantriketnoi", "sort_order": 23})
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

    def delete_feature(self, code: str) -> None:
        self._delete("user_permissions", {"feature_code": f"eq.{code}"})
        self._delete("features", {"code": f"eq.{code}"})

    def ensure_dashboard_layout_feature(self, page_id: str, page_name: str) -> str:
        code = dashboard_feature_code_for_page(page_id)
        existing = self._get("features", {"code": f"eq.{code}", "select": "code", "limit": "1"})
        existing_code = existing[0]["code"] if existing else None
        if not existing_code:
            for row in self._get("features", {"select": "code"}):
                if normalize_feature_code(row.get("code")) == code:
                    existing_code = row["code"]
                    break
        if existing_code:
            self._patch("features", {"code": f"eq.{existing_code}"}, {"name": page_name})
            code = existing_code
        else:
            siblings = self._get("features", {"parent_code": "eq.baocaomoi", "select": "sort_order"})
            max_order = max([int(row.get("sort_order") or 0) for row in siblings] or [35])
            self._insert("features", {
                "code": code,
                "name": page_name,
                "parent_code": "baocaomoi",
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

    def list_dashboard_layouts(self) -> list[dict[str, Any]]:
        return self._get("dashboard_layouts", {
            "select": "page_id,page_name,created_at,updated_at",
            "order": "updated_at.desc,page_name.asc",
        })

    def get_dashboard_layout(self, page_id: str) -> dict[str, Any] | None:
        rows = self._get("dashboard_layouts", {"page_id": f"eq.{page_id}", "limit": "1"})
        return self._decode_dashboard_layout(rows[0]) if rows else None

    def save_dashboard_layout(self, page_id: str, page_name: str, layout: dict[str, Any]) -> str:
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
            return self.ensure_dashboard_layout_feature(page_id, page_name)
        payload["created_at"] = now
        self._insert("dashboard_layouts", payload)
        return self.ensure_dashboard_layout_feature(page_id, page_name)

    def delete_dashboard_layout(self, page_id: str) -> None:
        self._delete("dashboard_layouts", {"page_id": f"eq.{page_id}"})
        self._delete("dashboard_chart_cache", {"page_id": f"eq.{page_id}"})

    def get_dashboard_chart_cache(self, chart_key: str) -> dict[str, Any] | None:
        rows = self._get("dashboard_chart_cache", {"chart_key": f"eq.{chart_key}", "limit": "1"})
        return self._decode_dashboard_chart_cache(rows[0]) if rows else None

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

    def health_check(self) -> dict[str, Any]:
        rows = self._get("features", {"select": "code", "limit": "1"})
        return {"ok": True, "backend": "supabase", "feature_rows_seen": len(rows)}

    @staticmethod
    def _decode_connection(row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = row.get("config") or {}
        return row

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
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")
