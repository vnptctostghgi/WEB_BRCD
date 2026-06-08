import hashlib
import hmac
import os
import sqlite3
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        calculated = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=16384,
            r=8,
            p=1,
        )
        return hmac.compare_digest(calculated.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


class AppRepository:
    """Data Access Layer cho tai khoan ung dung va audit log."""

    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self, admin_username: str, admin_password: str) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'viewer')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    must_change_password INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS website_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    url TEXT NOT NULL,
                    requires_otp INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS web_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    website_id INTEGER NOT NULL,
                    login_username TEXT NOT NULL,
                    encrypted_password TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, website_id, login_username),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(website_id) REFERENCES website_catalog(id)
                );

                CREATE TABLE IF NOT EXISTS features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    parent_code TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS user_permissions (
                    user_id INTEGER NOT NULL,
                    feature_code TEXT NOT NULL,
                    PRIMARY KEY(user_id, feature_code),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(feature_code) REFERENCES features(code)
                );

                CREATE TABLE IF NOT EXISTS system_roles (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS system_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    connection_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    config_json TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS data_regions (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_data_permissions (
                    user_id INTEGER NOT NULL,
                    region_code TEXT NOT NULL,
                    PRIMARY KEY(user_id, region_code),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(region_code) REFERENCES data_regions(code)
                );

                CREATE TABLE IF NOT EXISTS work_tasks (
                    task_id TEXT PRIMARY KEY,
                    ten_cong_viec TEXT NOT NULL,
                    schedule_type TEXT NOT NULL DEFAULT 'Daily',
                    run_time TEXT NOT NULL DEFAULT '07:00',
                    weekday TEXT NOT NULL DEFAULT '',
                    once_date TEXT NOT NULL DEFAULT '',
                    group_name TEXT NOT NULL DEFAULT '',
                    is_done INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_notified_date TEXT NOT NULL DEFAULT '',
                    last_notified_at TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS login_attempts (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    last_ip TEXT NOT NULL DEFAULT '',
                    last_failed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                """
            )
            for column, definition in {
                "employee_code": "TEXT COLLATE NOCASE",
                "email": "TEXT COLLATE NOCASE",
                "phone": "TEXT",
                "birth_date": "TEXT",
                "gender": "TEXT",
                "department": "TEXT",
                "job_title": "TEXT",
            }.items():
                try:
                    connection.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError:
                    pass
            connection.executemany(
                "INSERT OR IGNORE INTO features (code, name, parent_code, sort_order) VALUES (?, ?, ?, ?)",
                [
                    ("dashboard", "Tổng quan", None, 10),
                    ("vault", "Kho tài khoản web", None, 20),
                    ("vault.view", "Xem danh sách tài khoản", "vault", 21),
                    ("vault.manage", "Thêm và sửa tài khoản", "vault", 22),
                    ("vault.reveal", "Xem mật khẩu đã lưu", "vault", 23),
                    ("admin", "Quản trị", None, 30),
                    ("admin.users", "Quản trị người dùng", "admin", 31),
                    ("admin.catalogs", "Quản trị danh mục website", "admin", 32),
                    ("admin.permissions", "Phân quyền chức năng", "admin", 33),
                    ("admin.audit", "Xem nhật ký hoạt động", "admin", 34),
                    ("admin.connections", "Quản trị kết nối hệ thống", "admin", 35),
                    ("admin.connections.test", "Kiểm tra kết nối hệ thống", "admin.connections", 36),
                ],
            )
            connection.executemany(
                "INSERT OR IGNORE INTO features (code, name, parent_code, sort_order) VALUES (?, ?, ?, ?)",
                [
                    ("dashboard", "Tổng quan", None, 10),
                    ("admin.web", "Quản trị web", None, 20),
                    ("admin.users", "Quản trị người dùng", "admin.web", 21),
                    ("admin.connections", "Quản trị kết nối", "admin.web", 22),
                    ("admin.permissions", "Phân quyền người dùng", "admin.web", 23),
                    ("admin.data_permissions", "Phân quyền dữ liệu người dùng", "admin.web", 24),
                    ("admin.catalogs", "Quản trị danh mục", "admin.web", 25),
                    ("admin.roles", "Quản trị vai trò", "admin.catalogs", 26),
                    ("admin.menu", "Quản trị menu", "admin.web", 27),
                    ("admin.work_tasks", "Quản lý công việc", None, 28),
                    ("reports", "Báo cáo thống kê", None, 30),
                    ("vault", "Tài khoản web", None, 40),
                    ("vault.view", "Xem danh sách tài khoản", "vault", 41),
                    ("vault.manage", "Thêm và sửa tài khoản", "vault", 42),
                    ("vault.reveal", "Xem mật khẩu đã lưu", "vault", 43),
                    ("admin.audit", "Nhật ký hoạt động", "admin.web", 90),
                ],
            )
            connection.executemany(
                "UPDATE features SET name=? WHERE code=?",
                [
                    ("Tổng quan", "dashboard"),
                    ("Quản trị web", "admin.web"),
                    ("Quản trị người dùng", "admin.users"),
                    ("Quản trị kết nối", "admin.connections"),
                    ("Phân quyền người dùng", "admin.permissions"),
                    ("Phân quyền dữ liệu người dùng", "admin.data_permissions"),
                    ("Quản trị danh mục", "admin.catalogs"),
                    ("Quản trị vai trò", "admin.roles"),
                    ("Quản trị menu", "admin.menu"),
                    ("Quản lý công việc", "admin.work_tasks"),
                    ("Báo cáo thống kê", "reports"),
                    ("Tài khoản web", "vault"),
                    ("Xem danh sách tài khoản", "vault.view"),
                    ("Thêm và sửa tài khoản", "vault.manage"),
                    ("Xem mật khẩu đã lưu", "vault.reveal"),
                    ("Nhật ký hoạt động", "admin.audit"),
                ],
            )
            connection.execute("DROP TABLE IF EXISTS attt_exam_links")
            now = self._now()
            connection.executemany(
                """
                INSERT OR IGNORE INTO system_roles (code, name, description, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?, ?)
                """,
                [
                    ("admin", "Quản trị hệ thống", "Toàn quyền quản trị và cấu hình hệ thống.", 10, now, now),
                    ("region_manager", "Quản lý phân vùng", "Quản lý số liệu và người dùng theo phân vùng được cấp.", 20, now, now),
                    ("data_entry", "Nhân viên nhập liệu", "Nhập và kiểm tra dữ liệu nghiệp vụ.", 30, now, now),
                    ("viewer", "Người xem", "Xem báo cáo và chức năng được phân quyền.", 40, now, now),
                ],
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO data_regions (code, name, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                [("ALL", "Tat ca", 0, now, now), ("13", "Can Tho", 10, now, now), ("66", "Hau Giang", 20, now, now), ("47", "Soc Trang", 30, now, now)],
            )
            exists = connection.execute(
                "SELECT id FROM users WHERE username = ?", (admin_username,)
            ).fetchone()
            if not exists:
                now = self._now()
                connection.execute(
                    """
                    INSERT INTO users
                    (username, full_name, password_hash, role, is_active, must_change_password, created_at, updated_at)
                    VALUES (?, ?, ?, 'admin', 1, 1, ?, ?)
                    """,
                    (admin_username, "Quản trị viên hệ thống", hash_password(admin_password), now, now),
                )
            admin = connection.execute("SELECT id FROM users WHERE username = ?", (admin_username,)).fetchone()
            connection.execute(
                "INSERT OR IGNORE INTO user_permissions (user_id, feature_code) SELECT ?, code FROM features",
                (admin["id"],),
            )

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, username, full_name, employee_code, email, phone, birth_date, gender, department, job_title,
                       role, is_active, must_change_password, created_at, updated_at
                FROM users ORDER BY id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def create_user(self, username: str, full_name: str, password: str, role: str, employee: dict[str, Any] | None = None) -> int:
        now = self._now()
        employee = employee or {}
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users
                (username, full_name, employee_code, email, phone, birth_date, gender, department, job_title,
                 password_hash, role, is_active, must_change_password, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (
                    username, full_name, employee.get("employee_code"), employee.get("email"), employee.get("phone"),
                    employee.get("birth_date"), employee.get("gender"), employee.get("department"), employee.get("job_title"),
                    hash_password(password), role, now, now,
                ),
            )
            return int(cursor.lastrowid)

    def update_user(self, user_id: int, full_name: str, role: str, is_active: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE users SET full_name = ?, role = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (full_name, role, int(is_active), self._now(), user_id),
            )

    def delete_user(self, user_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM users WHERE id=?", (user_id,))

    def get_user_by_employee_or_email(self, employee_code: str, email: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE lower(employee_code)=lower(?) OR lower(email)=lower(?)",
                (employee_code, email),
            ).fetchone()
            return dict(row) if row else None

    def change_password(self, user_id: int, password: str, must_change: bool = False) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE users SET password_hash = ?, must_change_password = ?, updated_at = ?
                WHERE id = ?
                """,
                (hash_password(password), int(must_change), self._now(), user_id),
            )

    def count_active_admins(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()
            return int(row["total"])

    def add_audit_log(self, actor: str, action: str, details: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_logs (actor, action, details, created_at) VALUES (?, ?, ?, ?)",
                (actor, action, details, self._now()),
            )

    def record_login_failure(self, username: str, ip_address: str) -> int:
        now = self._now()
        normalized = (username or "unknown").strip().lower() or "unknown"
        with self.connect() as connection:
            row = connection.execute(
                "SELECT fail_count FROM login_attempts WHERE username=?",
                (normalized,),
            ).fetchone()
            fail_count = int(row["fail_count"]) + 1 if row else 1
            connection.execute(
                """
                INSERT INTO login_attempts (username, fail_count, last_ip, last_failed_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                  fail_count=excluded.fail_count,
                  last_ip=excluded.last_ip,
                  last_failed_at=excluded.last_failed_at,
                  updated_at=excluded.updated_at
                """,
                (normalized, fail_count, ip_address, now, now),
            )
            return fail_count

    def reset_login_failures(self, username: str) -> None:
        normalized = (username or "unknown").strip().lower() or "unknown"
        with self.connect() as connection:
            connection.execute("DELETE FROM login_attempts WHERE username=?", (normalized,))

    def list_audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def list_websites(self, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM website_catalog"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query).fetchall()]

    def get_website(self, website_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM website_catalog WHERE id = ?", (website_id,)).fetchone()
            return dict(row) if row else None

    def save_website(self, website_id: int | None, name: str, url: str, requires_otp: bool, is_active: bool) -> int:
        now = self._now()
        with self.connect() as connection:
            if website_id:
                connection.execute(
                    "UPDATE website_catalog SET name=?, url=?, requires_otp=?, is_active=?, updated_at=? WHERE id=?",
                    (name, url, int(requires_otp), int(is_active), now, website_id),
                )
                return website_id
            cursor = connection.execute(
                "INSERT INTO website_catalog (name, url, requires_otp, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, url, int(requires_otp), int(is_active), now, now),
            )
            return int(cursor.lastrowid)

    def list_credentials(self, user_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.website_id, c.login_username, c.notes, c.created_at, c.updated_at,
                       w.name AS website_name, w.url, w.requires_otp
                FROM web_credentials c JOIN website_catalog w ON w.id = c.website_id
                WHERE c.user_id = ? ORDER BY w.name, c.login_username
                """, (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_credential(self, credential_id: int, user_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM web_credentials WHERE id = ? AND user_id = ?", (credential_id, user_id)
            ).fetchone()
            return dict(row) if row else None

    def save_credential(self, credential_id: int | None, user_id: int, website_id: int, username: str, encrypted_password: str, notes: str) -> int:
        now = self._now()
        with self.connect() as connection:
            if credential_id:
                connection.execute(
                    "UPDATE web_credentials SET website_id=?, login_username=?, encrypted_password=?, notes=?, updated_at=? WHERE id=? AND user_id=?",
                    (website_id, username, encrypted_password, notes, now, credential_id, user_id),
                )
                return credential_id
            cursor = connection.execute(
                "INSERT INTO web_credentials (user_id, website_id, login_username, encrypted_password, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, website_id, username, encrypted_password, notes, now, now),
            )
            return int(cursor.lastrowid)

    def delete_credential(self, credential_id: int, user_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM web_credentials WHERE id=? AND user_id=?", (credential_id, user_id))

    def list_features(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM features ORDER BY sort_order").fetchall()]

    def update_feature_layout(self, code: str, name: str, parent_code: str | None, sort_order: int) -> None:
        with self.connect() as connection:
            parent = parent_code or None
            if parent == code:
                raise ValueError("Chức năng cha không được trùng chính nó.")
            connection.execute(
                "UPDATE features SET name=?, parent_code=?, sort_order=? WHERE code=?",
                (name, parent, sort_order, code),
            )

    def get_user_permissions(self, user_id: int) -> list[str]:
        with self.connect() as connection:
            return [row["feature_code"] for row in connection.execute(
                "SELECT feature_code FROM user_permissions WHERE user_id=? ORDER BY feature_code", (user_id,)
            ).fetchall()]

    def set_user_permissions(self, user_id: int, feature_codes: list[str]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM user_permissions WHERE user_id=?", (user_id,))
            connection.executemany(
                "INSERT INTO user_permissions (user_id, feature_code) VALUES (?, ?)",
                [(user_id, code) for code in feature_codes],
            )

    def set_bulk_user_permissions(self, user_ids: list[int], feature_codes: list[str]) -> None:
        with self.connect() as connection:
            for user_id in user_ids:
                connection.execute("DELETE FROM user_permissions WHERE user_id=?", (user_id,))
                connection.executemany(
                    "INSERT INTO user_permissions (user_id, feature_code) VALUES (?, ?)",
                    [(user_id, code) for code in feature_codes],
                )

    def list_system_roles(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM system_roles ORDER BY sort_order, code"
            ).fetchall()]

    def save_system_role(self, code: str, name: str, description: str, is_active: bool, sort_order: int) -> None:
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO system_roles (code, name, description, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET name=excluded.name, description=excluded.description,
                  is_active=excluded.is_active, sort_order=excluded.sort_order, updated_at=excluded.updated_at
                """,
                (code, name, description, int(is_active), sort_order, now, now),
            )

    def delete_system_role(self, code: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM system_roles WHERE code=?", (code,))

    def list_data_regions(self, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM data_regions"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY sort_order, code"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query).fetchall()]

    def save_data_region(self, code: str, name: str, is_active: bool, sort_order: int) -> None:
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO data_regions (code, name, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET name=excluded.name, is_active=excluded.is_active,
                  sort_order=excluded.sort_order, updated_at=excluded.updated_at
                """,
                (code, name, int(is_active), sort_order, now, now),
            )

    def delete_data_region(self, code: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM user_data_permissions WHERE region_code=?", (code,))
            connection.execute("DELETE FROM data_regions WHERE code=?", (code,))

    def get_user_data_permissions(self, user_id: int) -> list[str]:
        with self.connect() as connection:
            return [row["region_code"] for row in connection.execute(
                "SELECT region_code FROM user_data_permissions WHERE user_id=? ORDER BY region_code", (user_id,)
            ).fetchall()]

    def set_bulk_user_data_permissions(self, user_ids: list[int], region_codes: list[str]) -> None:
        with self.connect() as connection:
            for user_id in user_ids:
                connection.execute("DELETE FROM user_data_permissions WHERE user_id=?", (user_id,))
                connection.executemany(
                    "INSERT INTO user_data_permissions (user_id, region_code) VALUES (?, ?)",
                    [(user_id, code) for code in region_codes],
                )

    def list_system_connections(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM system_connections ORDER BY id").fetchall()
            return [self._decode_connection(dict(row)) for row in rows]

    def get_system_connection_by_code(self, code: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM system_connections WHERE code=?", (code,)).fetchone()
            return self._decode_connection(dict(row)) if row else None

    def upsert_system_connection(self, code: str, name: str, connection_type: str, description: str, config: dict[str, Any], is_active: bool) -> int:
        now = self._now()
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM system_connections WHERE code=?", (code,)).fetchone()
            payload = json.dumps(config, ensure_ascii=False)
            if row:
                connection.execute(
                    """
                    UPDATE system_connections
                    SET name=?, connection_type=?, description=?, config_json=?, is_active=?, updated_at=?
                    WHERE code=?
                    """,
                    (name, connection_type, description, payload, int(is_active), now, code),
                )
                return int(row["id"])
            cursor = connection.execute(
                """
                INSERT INTO system_connections
                (code, name, connection_type, description, config_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, name, connection_type, description, payload, int(is_active), now, now),
            )
            return int(cursor.lastrowid)

    def list_work_tasks(self, include_completed: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM work_tasks"
        if not include_completed:
            query += " WHERE is_active = 1 AND is_done = 0"
        query += " ORDER BY run_time, task_id"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
            return [self._decode_work_task(dict(row)) for row in rows]

    def get_work_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM work_tasks WHERE task_id=?", (task_id,)).fetchone()
            return self._decode_work_task(dict(row)) if row else None

    def generate_work_task_id(self) -> str:
        with self.connect() as connection:
            rows = connection.execute("SELECT task_id FROM work_tasks WHERE task_id LIKE 'TASK%'").fetchall()
        max_number = 0
        for row in rows:
            suffix = str(row["task_id"])[4:]
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"TASK{max_number + 1:04d}"

    def save_work_task(self, payload: dict[str, Any]) -> None:
        now = self._now()
        task_id = str(payload["task_id"]).strip()
        is_done = int(bool(payload.get("check", False)))
        is_active = 0 if is_done else int(bool(payload.get("is_active", True)))
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO work_tasks
                (task_id, ten_cong_viec, schedule_type, run_time, weekday, once_date, group_name,
                 is_done, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  ten_cong_viec=excluded.ten_cong_viec,
                  schedule_type=excluded.schedule_type,
                  run_time=excluded.run_time,
                  weekday=excluded.weekday,
                  once_date=excluded.once_date,
                  group_name=excluded.group_name,
                  is_done=excluded.is_done,
                  is_active=excluded.is_active,
                  updated_at=excluded.updated_at
                """,
                (
                    task_id,
                    str(payload.get("ten_cong_viec", "")).strip(),
                    str(payload.get("type", "Daily")).strip() or "Daily",
                    str(payload.get("time", "07:00")).strip() or "07:00",
                    str(payload.get("weekday", "")).strip(),
                    str(payload.get("once_date", "")).strip(),
                    str(payload.get("group", "")).strip(),
                    is_done,
                    is_active,
                    now,
                    now,
                ),
            )

    def delete_work_task(self, task_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM work_tasks WHERE task_id=?", (task_id,))

    def complete_work_task(self, task_id: str) -> None:
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE work_tasks
                SET is_done=1, is_active=0, completed_at=?, updated_at=?
                WHERE task_id=?
                """,
                (now, now, task_id),
            )

    def mark_work_task_notified(self, task_id: str, notified_date: str) -> None:
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE work_tasks
                SET last_notified_date=?, last_notified_at=?, updated_at=?
                WHERE task_id=?
                """,
                (notified_date, now, now, task_id),
            )

    @staticmethod
    def _decode_connection(row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = json.loads(row.pop("config_json") or "{}")
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
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")
