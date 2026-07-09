import hashlib
import hmac
import os
import sqlite3
import json
import re
import secrets
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FEATURE_ROWS = [
    ("dashboard", "Tổng quan", None, 10),
    ("quantriweb", "Quản trị web", None, 20),
    ("quantringuoidung", "Quản trị người dùng", "quantriweb", 21),
    ("quantriketnoi", "Quản trị kết nối", "quantriweb", 22),
    ("phanquyennguoidung", "Phân quyền người dùng", "quantriweb", 23),
    ("phanquyendulieunguoidung", "Phân quyền dữ liệu người dùng", "quantriweb", 24),
    ("quantridanhmuc", "Quản trị danh mục", "quantriweb", 25),
    ("quantrivaitro", "Quản trị vai trò", "quantridanhmuc", 26),
    ("quantrimenu", "Quản trị menu", "quantriweb", 27),
    ("quanlycongviec", "Quản lý công việc", None, 28),
    ("truyvansql", "Truy vấn SQL", None, 30),
    ("baocaomoi", "Báo cáo mới", None, 35),
    ("thietkelayoutbaocao", "Thiết kế Layout báo cáo", "baocaomoi", 36),
    ("daodulieuonebss", "Đào dữ liệu OneBSS", "baocaomoi", 37),
    ("taikhoanweb", "Tài khoản web", "quantriweb", 40),
    ("xemdanhsachtaikhoan", "Xem danh sách tài khoản", "taikhoanweb", 41),
    ("themvasuataikhoan", "Thêm và sửa tài khoản", "taikhoanweb", 42),
    ("xemmatkhaudaluu", "Xem mật khẩu đã lưu", "taikhoanweb", 43),
    ("nhatkyhoatdong", "Nhật ký hoạt động", "quantriweb", 90),
    ("quantrisql", "Quản trị SQL", "quantriketnoi", 23),
    ("quantridulieuonebss", "Quản trị dữ liệu OneBSS", "quantriketnoi", 24),
]

FEATURE_CODE_ALIASES = {
    "admin.web": "quantriweb",
    "admin.users": "quantringuoidung",
    "admin.connections": "quantriketnoi",
    "admin.permissions": "phanquyennguoidung",
    "admin.data_permissions": "phanquyendulieunguoidung",
    "admin.catalogs": "quantridanhmuc",
    "admin.roles": "quantrivaitro",
    "admin.menu": "quantrimenu",
    "admin.work_tasks": "quanlycongviec",
    "reports": "truyvansql",
    "new_reports": "baocaomoi",
    "admin.dashboard_builder": "thietkelayoutbaocao",
    "vault": "taikhoanweb",
    "vault.view": "xemdanhsachtaikhoan",
    "vault.manage": "themvasuataikhoan",
    "vault.reveal": "xemmatkhaudaluu",
    "admin.audit": "nhatkyhoatdong",
    "admin.sql_reports": "quantrisql",
    "admin.onebss_reports": "quantridulieuonebss",
    "web_links": "lienketweb",
    "web_links.elearning": "elearning",
}

LEGACY_REMOVED_FEATURE_CODES = (
    "admin",
    "admin.connections.test",
    "auto",
    "auto.attt_quarterly",
    "auto.attt_links",
)

OBSOLETE_FEATURE_CODES = (
    *LEGACY_REMOVED_FEATURE_CODES,
    *FEATURE_CODE_ALIASES.keys(),
)

DEFAULT_DASHBOARD_PAGE_ID = "DASHBOARD_KINH_DOANH"
DEFAULT_DASHBOARD_PAGE_NAME = "Dashboard Kinh doanh"
DEFAULT_DASHBOARD_LAYOUT = {
    "page_id": DEFAULT_DASHBOARD_PAGE_ID,
    "tabs": [
        {
            "tab_id": "tab_doanh_thu",
            "tab_name": "Doanh Thu Lõi",
            "order": 1,
            "grid_layout": [
                {
                    "row_id": 1,
                    "layout_type": "2_columns",
                    "widgets": [
                        {"position": 1, "type": "bar_chart", "title": "Di động", "sql_code": "BC_DI_DONG"},
                        {"position": 2, "type": "pie_chart", "title": "Băng rộng", "sql_code": "BC_BANG_RONG"},
                    ],
                }
            ],
        },
        {
            "tab_id": "tab_san_luong",
            "tab_name": "Sản lượng",
            "order": 2,
            "grid_layout": [
                {
                    "row_id": 1,
                    "layout_type": "4_columns",
                    "widgets": [
                        {"position": 1, "type": "metric", "title": "Fiber", "sql_code": "DASHBOARD_FIBER_VNPT"},
                        {"position": 2, "type": "metric", "title": "MyTV", "sql_code": "BC_MYTV"},
                        {"position": 3, "type": "metric", "title": "Mesh", "sql_code": "BC_MESH"},
                        {"position": 4, "type": "metric", "title": "CAM", "sql_code": "BC_CAM"},
                    ],
                }
            ],
        },
    ],
}


def dashboard_feature_code_for_page(page_id: str) -> str:
    normalized_page_id = re.sub(r"[^A-Za-z0-9]+", "", page_id).upper()
    if normalized_page_id == re.sub(r"[^A-Za-z0-9]+", "", DEFAULT_DASHBOARD_PAGE_ID).upper():
        return "dashboard"
    if normalized_page_id == "REPORTS":
        return "truyvansql"
    return normalize_feature_code(page_id) or normalize_feature_code(DEFAULT_DASHBOARD_PAGE_ID)


def normalize_feature_code(value: Any) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    alias = FEATURE_CODE_ALIASES.get(raw_value)
    if alias:
        return alias
    ascii_value = unicodedata.normalize("NFD", raw_value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "", ascii_value).lower()


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

                CREATE TABLE IF NOT EXISTS sql_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ten_bao_cao TEXT NOT NULL,
                    ma_bao_cao TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    cau_lenh_sql TEXT NOT NULL,
                    cac_tham_so TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS onebss_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ma_bao_cao TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    ten_bao_cao TEXT NOT NULL,
                    danh_sach_bien_json TEXT NOT NULL DEFAULT '[]',
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    report_url TEXT NOT NULL,
                    storage_link TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS onebss_report_runs (
                    run_id TEXT PRIMARY KEY,
                    ma_bao_cao TEXT NOT NULL,
                    ten_bao_cao TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    file_name TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    storage_link TEXT NOT NULL DEFAULT '',
                    storage_status TEXT NOT NULL DEFAULT '',
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS onebss_report_runs_report_idx
                ON onebss_report_runs (ma_bao_cao, started_at DESC);

                CREATE TABLE IF NOT EXISTS dashboard_layouts (
                    page_id TEXT PRIMARY KEY,
                    page_name TEXT NOT NULL,
                    layout_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dashboard_chart_cache (
                    chart_key TEXT PRIMARY KEY,
                    page_id TEXT NOT NULL,
                    tab_id TEXT NOT NULL,
                    widget_key TEXT NOT NULL,
                    report_id INTEGER,
                    sql_code TEXT NOT NULL,
                    report_code TEXT,
                    report_name TEXT,
                    widget_title TEXT,
                    widget_type TEXT,
                    filters_json TEXT NOT NULL DEFAULT '{}',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'success',
                    error_message TEXT,
                    duration_ms INTEGER,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    refreshed_at TEXT NOT NULL,
                    expires_at TEXT,
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

                CREATE TABLE IF NOT EXISTS zalo_auto_messages (
                    schedule_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    page_url TEXT NOT NULL DEFAULT '/',
                    page_label TEXT NOT NULL DEFAULT '',
                    schedule_type TEXT NOT NULL DEFAULT 'Daily',
                    time_slots_json TEXT NOT NULL DEFAULT '[]',
                    run_time TEXT NOT NULL DEFAULT '07:00',
                    weekday TEXT NOT NULL DEFAULT '',
                    month_day INTEGER NOT NULL DEFAULT 1,
                    target_type TEXT NOT NULL DEFAULT 'group',
                    chat_id TEXT NOT NULL DEFAULT '',
                    chat_name TEXT NOT NULL DEFAULT '',
                    caption TEXT NOT NULL DEFAULT '',
                    photo_url TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_run_key TEXT NOT NULL DEFAULT '',
                    last_sent_key TEXT NOT NULL DEFAULT '',
                    last_sent_at TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS zalo_message_captures (
                    capture_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL,
                    mime_type TEXT NOT NULL DEFAULT 'image/png',
                    image_base64 TEXT NOT NULL,
                    public_token TEXT NOT NULL UNIQUE,
                    page_url TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(schedule_id) REFERENCES zalo_auto_messages(schedule_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS zalo_message_captures_schedule_idx
                ON zalo_message_captures (schedule_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS data_mining_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    report_url TEXT NOT NULL,
                    schedule_type TEXT NOT NULL DEFAULT 'Daily',
                    run_time TEXT NOT NULL DEFAULT '07:00',
                    weekday TEXT NOT NULL DEFAULT '',
                    month_day INTEGER NOT NULL DEFAULT 1,
                    storage_link TEXT NOT NULL DEFAULT '',
                    file_name_template TEXT NOT NULL DEFAULT '',
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_run_key TEXT NOT NULL DEFAULT '',
                    last_success_key TEXT NOT NULL DEFAULT '',
                    last_run_at TEXT NOT NULL DEFAULT '',
                    last_success_at TEXT NOT NULL DEFAULT '',
                    last_status TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    last_file_name TEXT NOT NULL DEFAULT '',
                    last_file_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS data_mining_runs (
                    run_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    message TEXT NOT NULL DEFAULT '',
                    file_name TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    storage_link TEXT NOT NULL DEFAULT '',
                    storage_status TEXT NOT NULL DEFAULT '',
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(schedule_id) REFERENCES data_mining_schedules(schedule_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS data_mining_runs_schedule_idx
                ON data_mining_runs (schedule_id, started_at DESC);

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
            try:
                connection.execute("ALTER TABLE onebss_reports ADD COLUMN parameters_json TEXT NOT NULL DEFAULT '{}'")
            except sqlite3.OperationalError:
                pass
            legacy_menu = connection.execute(
                "SELECT 1 FROM features WHERE code IN ('admin', 'admin.connections.test', 'admin.menu', 'new_reports') LIMIT 1"
            ).fetchone()
            self._migrate_feature_codes(connection)
            connection.executemany(
                "INSERT OR IGNORE INTO features (code, name, parent_code, sort_order) VALUES (?, ?, ?, ?)",
                FEATURE_ROWS,
            )
            if legacy_menu:
                connection.executemany(
                    "UPDATE features SET name=?, parent_code=?, sort_order=? WHERE code=?",
                    [(name, parent_code, sort_order, code) for code, name, parent_code, sort_order in FEATURE_ROWS],
                )
            connection.execute("UPDATE features SET name='Truy vấn SQL' WHERE code='truyvansql'")
            connection.execute("UPDATE features SET name='Báo cáo mới' WHERE code='baocaomoi'")
            connection.execute(
                "UPDATE features SET parent_code='baocaomoi', sort_order=36 WHERE code='thietkelayoutbaocao' AND parent_code='truyvansql'"
            )
            connection.execute("UPDATE features SET parent_code='baocaomoi' WHERE parent_code='truyvansql'")
            connection.executemany(
                "DELETE FROM user_permissions WHERE feature_code=?",
                [(code,) for code in OBSOLETE_FEATURE_CODES],
            )
            connection.executemany(
                "DELETE FROM features WHERE code=?",
                [(code,) for code in OBSOLETE_FEATURE_CODES],
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
            connection.execute(
                """
                INSERT OR IGNORE INTO dashboard_layouts
                (page_id, page_name, layout_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    DEFAULT_DASHBOARD_PAGE_ID,
                    DEFAULT_DASHBOARD_PAGE_NAME,
                    json.dumps(DEFAULT_DASHBOARD_LAYOUT, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def _migrate_feature_codes(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT code, name, parent_code, sort_order FROM features"
        ).fetchall()
        migrations: dict[str, str] = {}
        for row in rows:
            old_code = str(row["code"])
            if old_code in LEGACY_REMOVED_FEATURE_CODES:
                continue
            new_code = normalize_feature_code(old_code)
            if not new_code or new_code == old_code:
                continue
            migrations[old_code] = new_code
            existing = connection.execute(
                "SELECT code FROM features WHERE code=?", (new_code,)
            ).fetchone()
            if not existing:
                parent_code = normalize_feature_code(row["parent_code"]) or None
                connection.execute(
                    """
                    INSERT OR IGNORE INTO features (code, name, parent_code, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (new_code, row["name"], parent_code, row["sort_order"]),
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO user_permissions (user_id, feature_code)
                SELECT user_id, ? FROM user_permissions WHERE feature_code=?
                """,
                (new_code, old_code),
            )

        for old_code, new_code in migrations.items():
            connection.execute(
                "UPDATE features SET parent_code=? WHERE parent_code=?",
                (new_code, old_code),
            )
        for old_code in migrations:
            connection.execute("DELETE FROM user_permissions WHERE feature_code=?", (old_code,))
            connection.execute("DELETE FROM features WHERE code=?", (old_code,))

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

    def create_menu_feature(self, name: str) -> dict[str, Any]:
        menu_name = name.strip()
        if not menu_name:
            raise ValueError("Tên menu không được để trống.")
        base_code = normalize_feature_code(menu_name) or "menu"
        with self.connect() as connection:
            existing_rows = connection.execute("SELECT code FROM features").fetchall()
            existing_codes = {str(row["code"] or "") for row in existing_rows}
            existing_normalized_codes = {normalize_feature_code(code) for code in existing_codes}
            code = base_code
            suffix = 2
            while code in existing_codes or normalize_feature_code(code) in existing_normalized_codes:
                code = f"{base_code}{suffix}"
                suffix += 1
            max_order = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM features WHERE parent_code IS NULL"
            ).fetchone()["max_order"]
            connection.execute(
                """
                INSERT INTO features (code, name, parent_code, sort_order)
                VALUES (?, ?, NULL, ?)
                """,
                (code, menu_name, int(max_order or 0) + 10),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO user_permissions (user_id, feature_code)
                SELECT id, ? FROM users WHERE role='admin'
                """,
                (code,),
            )
            row = connection.execute("SELECT * FROM features WHERE code=?", (code,)).fetchone()
            return dict(row)

    def delete_feature(self, code: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM user_permissions WHERE feature_code=?", (code,))
            connection.execute("DELETE FROM features WHERE code=?", (code,))

    def ensure_dashboard_layout_feature(self, page_id: str, page_name: str, parent_code: str | None = None) -> str:
        code = dashboard_feature_code_for_page(page_id)
        selected_parent = None
        if parent_code is not None:
            selected_parent = normalize_feature_code(parent_code) or "baocaomoi"
        with self.connect() as connection:
            existing = connection.execute("SELECT code, parent_code FROM features WHERE code=?", (code,)).fetchone()
            existing_code = existing["code"] if existing else None
            existing_parent = existing["parent_code"] if existing else None
            if not existing_code:
                rows = connection.execute("SELECT code, parent_code FROM features").fetchall()
                for row in rows:
                    if normalize_feature_code(row["code"]) == code:
                        existing_code = row["code"]
                        existing_parent = row["parent_code"]
                        break
            if existing_code:
                if selected_parent is not None and selected_parent == existing_code:
                    raise ValueError("Mục menu cha không được trùng với layout đang lưu.")
                if selected_parent is None:
                    connection.execute("UPDATE features SET name=? WHERE code=?", (page_name, existing_code))
                elif selected_parent != existing_parent:
                    max_order = connection.execute(
                        "SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM features WHERE parent_code=?",
                        (selected_parent,),
                    ).fetchone()["max_order"]
                    connection.execute(
                        "UPDATE features SET name=?, parent_code=?, sort_order=? WHERE code=?",
                        (page_name, selected_parent, int(max_order or 0) + 10, existing_code),
                    )
                else:
                    connection.execute(
                        "UPDATE features SET name=?, parent_code=? WHERE code=?",
                        (page_name, selected_parent, existing_code),
                    )
                code = existing_code
            else:
                selected_parent = selected_parent or "baocaomoi"
                if selected_parent == code:
                    raise ValueError("Mục menu cha không được trùng với layout đang lưu.")
                max_order = connection.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM features WHERE parent_code=?",
                    (selected_parent,),
                ).fetchone()["max_order"]
                connection.execute(
                    """
                    INSERT INTO features (code, name, parent_code, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (code, page_name, selected_parent, int(max_order or 0) + 10),
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO user_permissions (user_id, feature_code)
                SELECT id, ? FROM users WHERE role='admin'
                """,
                (code,),
            )
        return code

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

    def list_sql_reports(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM sql_reports ORDER BY ten_bao_cao").fetchall()
            return [self._decode_sql_report(dict(row)) for row in rows]

    def get_sql_report_by_id(self, report_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sql_reports WHERE id=?", (report_id,)).fetchone()
            return self._decode_sql_report(dict(row)) if row else None

    def get_sql_report_by_code(self, ma_bao_cao: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sql_reports WHERE ma_bao_cao=?", (ma_bao_cao,)).fetchone()
            return self._decode_sql_report(dict(row)) if row else None

    def save_sql_report(
        self,
        report_id: int | None,
        ten_bao_cao: str,
        ma_bao_cao: str,
        cau_lenh_sql: str,
        cac_tham_so: list[str],
    ) -> int:
        now = self._now()
        params_payload = json.dumps(cac_tham_so, ensure_ascii=False)
        with self.connect() as connection:
            if report_id:
                connection.execute(
                    """
                    UPDATE sql_reports
                    SET ten_bao_cao=?, ma_bao_cao=?, cau_lenh_sql=?, cac_tham_so=?, updated_at=?
                    WHERE id=?
                    """,
                    (ten_bao_cao, ma_bao_cao, cau_lenh_sql, params_payload, now, report_id),
                )
                return int(report_id)
            cursor = connection.execute(
                """
                INSERT INTO sql_reports
                (ten_bao_cao, ma_bao_cao, cau_lenh_sql, cac_tham_so, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ten_bao_cao, ma_bao_cao, cau_lenh_sql, params_payload, now, now),
            )
            return int(cursor.lastrowid)

    def delete_sql_report(self, report_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sql_reports WHERE id=?", (report_id,))

    def list_onebss_reports(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM onebss_reports ORDER BY ten_bao_cao").fetchall()
            return [self._decode_onebss_report(dict(row)) for row in rows]

    def get_onebss_report_by_id(self, report_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM onebss_reports WHERE id=?", (report_id,)).fetchone()
            return self._decode_onebss_report(dict(row)) if row else None

    def get_onebss_report_by_code(self, ma_bao_cao: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM onebss_reports WHERE ma_bao_cao=?", (ma_bao_cao,)).fetchone()
            return self._decode_onebss_report(dict(row)) if row else None

    def generate_onebss_report_code(self) -> str:
        with self.connect() as connection:
            rows = connection.execute("SELECT ma_bao_cao FROM onebss_reports WHERE ma_bao_cao LIKE 'ONEBSS%'").fetchall()
        numbers = []
        for row in rows:
            match = re.search(r"(\d+)$", str(row["ma_bao_cao"] or ""))
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
    ) -> int:
        now = self._now()
        params_payload = json.dumps(danh_sach_bien, ensure_ascii=False)
        parameters_payload = json.dumps(parameters if isinstance(parameters, dict) else {}, ensure_ascii=False)
        with self.connect() as connection:
            if report_id:
                connection.execute(
                    """
                    UPDATE onebss_reports
                    SET ma_bao_cao=?, ten_bao_cao=?, danh_sach_bien_json=?, parameters_json=?, report_url=?, storage_link=?, updated_at=?
                    WHERE id=?
                    """,
                    (ma_bao_cao, ten_bao_cao, params_payload, parameters_payload, report_url, storage_link, now, report_id),
                )
                return int(report_id)
            cursor = connection.execute(
                """
                INSERT INTO onebss_reports
                (ma_bao_cao, ten_bao_cao, danh_sach_bien_json, parameters_json, report_url, storage_link, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ma_bao_cao, ten_bao_cao, params_payload, parameters_payload, report_url, storage_link, now, now),
            )
            return int(cursor.lastrowid)

    def delete_onebss_report(self, report_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM onebss_reports WHERE id=?", (report_id,))

    def save_onebss_report_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = self._now()
        run_id = str(payload.get("run_id") or f"OBRUN{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}")
        parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
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
            "parameters_json": json.dumps(parameters, ensure_ascii=False),
            "started_at": str(payload.get("started_at") or now),
            "finished_at": str(payload.get("finished_at") or now),
            "duration_ms": int(payload.get("duration_ms") or 0),
            "created_by": str(payload.get("created_by") or ""),
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO onebss_report_runs
                (run_id, ma_bao_cao, ten_bao_cao, status, message, file_name, file_path, storage_link,
                 storage_status, parameters_json, started_at, finished_at, duration_ms, created_by)
                VALUES (:run_id, :ma_bao_cao, :ten_bao_cao, :status, :message, :file_name, :file_path, :storage_link,
                        :storage_status, :parameters_json, :started_at, :finished_at, :duration_ms, :created_by)
                """,
                row,
            )
        return self._decode_onebss_report_run(row)

    def list_onebss_report_runs(self, ma_bao_cao: str = "", limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = min(max(int(limit or 50), 1), 200)
        with self.connect() as connection:
            if ma_bao_cao:
                rows = connection.execute(
                    "SELECT * FROM onebss_report_runs WHERE ma_bao_cao=? ORDER BY started_at DESC LIMIT ?",
                    (ma_bao_cao, safe_limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM onebss_report_runs ORDER BY started_at DESC LIMIT ?",
                    (safe_limit,),
                ).fetchall()
            return [self._decode_onebss_report_run(dict(row)) for row in rows]

    def list_dashboard_layouts(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT page_id, page_name, created_at, updated_at
                FROM dashboard_layouts
                ORDER BY updated_at DESC, page_name
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_dashboard_layout(self, page_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM dashboard_layouts WHERE page_id=?",
                (page_id,),
            ).fetchone()
            return self._decode_dashboard_layout(dict(row)) if row else None

    def save_dashboard_layout(self, page_id: str, page_name: str, layout: dict[str, Any], parent_code: str | None = None) -> str:
        now = self._now()
        payload = json.dumps(layout, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dashboard_layouts (page_id, page_name, layout_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(page_id) DO UPDATE SET
                  page_name=excluded.page_name,
                  layout_json=excluded.layout_json,
                  updated_at=excluded.updated_at
                """,
                (page_id, page_name, payload, now, now),
            )
        return self.ensure_dashboard_layout_feature(page_id, page_name, parent_code)

    def delete_dashboard_layout(self, page_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM dashboard_layouts WHERE page_id=?", (page_id,))
            connection.execute("DELETE FROM dashboard_chart_cache WHERE page_id=?", (page_id,))

    def get_dashboard_chart_cache(self, chart_key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM dashboard_chart_cache WHERE chart_key=?",
                (chart_key,),
            ).fetchone()
            return self._decode_dashboard_chart_cache(dict(row)) if row else None

    def get_dashboard_chart_cache_many(self, chart_keys: list[str]) -> list[dict[str, Any]]:
        keys = [str(key) for key in chart_keys if str(key)]
        if not keys:
            return []
        placeholders = ",".join("?" for _ in keys)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM dashboard_chart_cache WHERE chart_key IN ({placeholders})",
                keys,
            ).fetchall()
            return [self._decode_dashboard_chart_cache(dict(row)) for row in rows]

    def upsert_dashboard_chart_cache(self, entry: dict[str, Any]) -> None:
        now = self._now()
        payload = {
            **entry,
            "filters_json": json.dumps(entry.get("filters") or {}, ensure_ascii=False),
            "payload_json": json.dumps(entry.get("payload") or {}, ensure_ascii=False),
            "created_at": entry.get("created_at") or now,
            "updated_at": entry.get("updated_at") or now,
            "refreshed_at": entry.get("refreshed_at") or now,
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dashboard_chart_cache
                (chart_key, page_id, tab_id, widget_key, report_id, sql_code, report_code, report_name,
                 widget_title, widget_type, filters_json, payload_json, status, error_message,
                 duration_ms, row_count, refreshed_at, expires_at, created_at, updated_at)
                VALUES (:chart_key, :page_id, :tab_id, :widget_key, :report_id, :sql_code, :report_code, :report_name,
                        :widget_title, :widget_type, :filters_json, :payload_json, :status, :error_message,
                        :duration_ms, :row_count, :refreshed_at, :expires_at, :created_at, :updated_at)
                ON CONFLICT(chart_key) DO UPDATE SET
                  page_id=excluded.page_id,
                  tab_id=excluded.tab_id,
                  widget_key=excluded.widget_key,
                  report_id=excluded.report_id,
                  sql_code=excluded.sql_code,
                  report_code=excluded.report_code,
                  report_name=excluded.report_name,
                  widget_title=excluded.widget_title,
                  widget_type=excluded.widget_type,
                  filters_json=excluded.filters_json,
                  payload_json=excluded.payload_json,
                  status=excluded.status,
                  error_message=excluded.error_message,
                  duration_ms=excluded.duration_ms,
                  row_count=excluded.row_count,
                  refreshed_at=excluded.refreshed_at,
                  expires_at=excluded.expires_at,
                  updated_at=excluded.updated_at
                """,
                payload,
            )

    def list_dashboard_chart_cache_keys(self, page_id: str | None = None) -> list[str]:
        with self.connect() as connection:
            if page_id:
                rows = connection.execute(
                    "SELECT chart_key FROM dashboard_chart_cache WHERE page_id=?",
                    (page_id,),
                ).fetchall()
            else:
                rows = connection.execute("SELECT chart_key FROM dashboard_chart_cache").fetchall()
            return [str(row["chart_key"]) for row in rows]

    def delete_dashboard_chart_cache(self, chart_key: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM dashboard_chart_cache WHERE chart_key=?", (chart_key,))

    def delete_dashboard_chart_cache_for_sql_report(self, report_id: int | None = None, report_codes: list[str] | None = None) -> int:
        conditions: list[str] = []
        params: list[Any] = []
        if report_id:
            conditions.append("report_id=?")
            params.append(report_id)
        codes = sorted({str(code or "").strip().upper() for code in (report_codes or []) if str(code or "").strip()})
        if codes:
            placeholders = ",".join("?" for _ in codes)
            conditions.append(f"(UPPER(report_code) IN ({placeholders}) OR UPPER(sql_code) IN ({placeholders}))")
            params.extend(codes)
            params.extend(codes)
        if not conditions:
            return 0
        with self.connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM dashboard_chart_cache WHERE {' OR '.join(conditions)}",
                params,
            )
            return int(cursor.rowcount or 0)

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

    def list_zalo_auto_messages(self, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM zalo_auto_messages"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY run_time, schedule_id"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
            return [self._decode_zalo_auto_message(dict(row)) for row in rows]

    def get_zalo_auto_message(self, schedule_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM zalo_auto_messages WHERE schedule_id=?", (schedule_id,)).fetchone()
            return self._decode_zalo_auto_message(dict(row)) if row else None

    def generate_zalo_auto_message_id(self) -> str:
        with self.connect() as connection:
            rows = connection.execute("SELECT schedule_id FROM zalo_auto_messages WHERE schedule_id LIKE 'ZALO%'").fetchall()
        max_number = 0
        for row in rows:
            suffix = str(row["schedule_id"])[4:]
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"ZALO{max_number + 1:04d}"

    def save_zalo_auto_message(self, payload: dict[str, Any]) -> None:
        now = self._now()
        schedule_id = str(payload["schedule_id"]).strip()
        time_slots = payload.get("time_slots") if isinstance(payload.get("time_slots"), list) else []
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO zalo_auto_messages
                (schedule_id, name, page_url, page_label, schedule_type, time_slots_json, run_time,
                 weekday, month_day, target_type, chat_id, chat_name, caption, photo_url,
                 is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id) DO UPDATE SET
                  name=excluded.name,
                  page_url=excluded.page_url,
                  page_label=excluded.page_label,
                  schedule_type=excluded.schedule_type,
                  time_slots_json=excluded.time_slots_json,
                  run_time=excluded.run_time,
                  weekday=excluded.weekday,
                  month_day=excluded.month_day,
                  target_type=excluded.target_type,
                  chat_id=excluded.chat_id,
                  chat_name=excluded.chat_name,
                  caption=excluded.caption,
                  photo_url=excluded.photo_url,
                  is_active=excluded.is_active,
                  updated_at=excluded.updated_at
                """,
                (
                    schedule_id,
                    str(payload.get("name", "")).strip(),
                    str(payload.get("page_url", "/")).strip() or "/",
                    str(payload.get("page_label", "")).strip(),
                    str(payload.get("schedule_type", "Daily")).strip() or "Daily",
                    json.dumps(time_slots, ensure_ascii=False),
                    str(payload.get("run_time", "07:00")).strip() or "07:00",
                    str(payload.get("weekday", "")).strip(),
                    int(payload.get("month_day") or 1),
                    str(payload.get("target_type", "group")).strip() or "group",
                    str(payload.get("chat_id", "")).strip(),
                    str(payload.get("chat_name", "")).strip(),
                    str(payload.get("caption", "")).strip(),
                    str(payload.get("photo_url", "")).strip(),
                    int(bool(payload.get("is_active", True))),
                    now,
                    now,
                ),
            )

    def delete_zalo_auto_message(self, schedule_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM zalo_auto_messages WHERE schedule_id=?", (schedule_id,))

    def mark_zalo_auto_message_run(self, schedule_id: str, run_key: str, ok: bool, error_message: str = "") -> None:
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE zalo_auto_messages
                SET last_run_key=?,
                    last_sent_key=CASE WHEN ? THEN ? ELSE last_sent_key END,
                    last_sent_at=CASE WHEN ? THEN ? ELSE last_sent_at END,
                    last_error=?,
                    updated_at=?
                WHERE schedule_id=?
                """,
                (run_key, int(ok), run_key, int(ok), now, str(error_message or "")[:500], now, schedule_id),
            )

    def save_zalo_message_capture(self, schedule_id: str, image_base64: str, mime_type: str, page_url: str = "", created_by: str = "") -> dict[str, Any]:
        capture_id = f"CAP{uuid.uuid4().hex[:16].upper()}"
        now = self._now()
        public_token = secrets.token_urlsafe(24)
        row = {
            "capture_id": capture_id,
            "schedule_id": schedule_id,
            "mime_type": mime_type or "image/png",
            "image_base64": image_base64,
            "public_token": public_token,
            "page_url": page_url or "",
            "created_by": created_by or "",
            "created_at": now,
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO zalo_message_captures
                (capture_id, schedule_id, mime_type, image_base64, public_token, page_url, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["capture_id"],
                    row["schedule_id"],
                    row["mime_type"],
                    row["image_base64"],
                    row["public_token"],
                    row["page_url"],
                    row["created_by"],
                    row["created_at"],
                ),
            )
        return self._decode_zalo_capture(row, include_image=False)

    def get_latest_zalo_message_capture(self, schedule_id: str, include_image: bool = False) -> dict[str, Any] | None:
        columns = "*" if include_image else "capture_id, schedule_id, mime_type, public_token, page_url, created_by, created_at"
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT {columns} FROM zalo_message_captures WHERE schedule_id=? ORDER BY created_at DESC LIMIT 1",
                (schedule_id,),
            ).fetchone()
            return self._decode_zalo_capture(dict(row), include_image=include_image) if row else None

    def get_zalo_message_capture(self, capture_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM zalo_message_captures WHERE capture_id=?", (capture_id,)).fetchone()
            return self._decode_zalo_capture(dict(row), include_image=True) if row else None

    def list_data_mining_schedules(self, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM data_mining_schedules"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY run_time, schedule_id"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
            return [self._decode_data_mining_schedule(dict(row)) for row in rows]

    def get_data_mining_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM data_mining_schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
            return self._decode_data_mining_schedule(dict(row)) if row else None

    def generate_data_mining_schedule_id(self) -> str:
        with self.connect() as connection:
            rows = connection.execute("SELECT schedule_id FROM data_mining_schedules WHERE schedule_id LIKE 'MINE%'").fetchall()
        max_number = 0
        for row in rows:
            suffix = str(row["schedule_id"])[4:]
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"MINE{max_number + 1:04d}"

    def save_data_mining_schedule(self, payload: dict[str, Any]) -> None:
        now = self._now()
        schedule_id = str(payload["schedule_id"]).strip()
        parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO data_mining_schedules
                (schedule_id, name, report_url, schedule_type, run_time, weekday, month_day,
                 storage_link, file_name_template, parameters_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id) DO UPDATE SET
                  name=excluded.name,
                  report_url=excluded.report_url,
                  schedule_type=excluded.schedule_type,
                  run_time=excluded.run_time,
                  weekday=excluded.weekday,
                  month_day=excluded.month_day,
                  storage_link=excluded.storage_link,
                  file_name_template=excluded.file_name_template,
                  parameters_json=excluded.parameters_json,
                  is_active=excluded.is_active,
                  updated_at=excluded.updated_at
                """,
                (
                    schedule_id,
                    str(payload.get("name", "")).strip(),
                    str(payload.get("report_url", "")).strip(),
                    str(payload.get("schedule_type", "Daily")).strip() or "Daily",
                    str(payload.get("run_time", "07:00")).strip() or "07:00",
                    str(payload.get("weekday", "")).strip(),
                    int(payload.get("month_day") or 1),
                    str(payload.get("storage_link", "")).strip(),
                    str(payload.get("file_name_template", "")).strip(),
                    json.dumps(parameters, ensure_ascii=False),
                    int(bool(payload.get("is_active", True))),
                    now,
                    now,
                ),
            )

    def delete_data_mining_schedule(self, schedule_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM data_mining_runs WHERE schedule_id=?", (schedule_id,))
            connection.execute("DELETE FROM data_mining_schedules WHERE schedule_id=?", (schedule_id,))

    def create_data_mining_run(self, schedule_id: str, parameters: dict[str, Any] | None = None, created_by: str = "") -> dict[str, Any]:
        now = self._now()
        run = {
            "run_id": f"RUN{uuid.uuid4().hex[:16].upper()}",
            "schedule_id": schedule_id,
            "status": "running",
            "message": "",
            "file_name": "",
            "file_path": "",
            "storage_link": "",
            "storage_status": "",
            "parameters": parameters if isinstance(parameters, dict) else {},
            "started_at": now,
            "finished_at": "",
            "duration_ms": 0,
            "created_by": created_by or "",
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO data_mining_runs
                (run_id, schedule_id, status, message, file_name, file_path, storage_link,
                 storage_status, parameters_json, started_at, finished_at, duration_ms, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run["run_id"],
                    run["schedule_id"],
                    run["status"],
                    run["message"],
                    run["file_name"],
                    run["file_path"],
                    run["storage_link"],
                    run["storage_status"],
                    json.dumps(run["parameters"], ensure_ascii=False),
                    run["started_at"],
                    run["finished_at"],
                    run["duration_ms"],
                    run["created_by"],
                ),
            )
        return run

    def finish_data_mining_run(self, run_id: str, result: dict[str, Any]) -> None:
        now = self._now()
        with self.connect() as connection:
            started = connection.execute("SELECT started_at FROM data_mining_runs WHERE run_id=?", (run_id,)).fetchone()
            duration_ms = int(result.get("duration_ms") or 0)
            if started and not duration_ms:
                try:
                    started_at = datetime.fromisoformat(str(started["started_at"]))
                    duration_ms = max(0, int((datetime.now(UTC) - started_at).total_seconds() * 1000))
                except ValueError:
                    duration_ms = 0
            connection.execute(
                """
                UPDATE data_mining_runs
                SET status=?, message=?, file_name=?, file_path=?, storage_link=?,
                    storage_status=?, finished_at=?, duration_ms=?
                WHERE run_id=?
                """,
                (
                    str(result.get("status") or ("success" if result.get("ok") else "failed"))[:50],
                    str(result.get("message") or "")[:1000],
                    str(result.get("file_name") or "")[:255],
                    str(result.get("file_path") or "")[:1000],
                    str(result.get("storage_link") or "")[:1000],
                    str(result.get("storage_status") or "")[:255],
                    now,
                    duration_ms,
                    run_id,
                ),
            )

    def mark_data_mining_schedule_run(self, schedule_id: str, run_key: str, ok: bool, result: dict[str, Any]) -> None:
        now = self._now()
        status_text = "success" if ok else str(result.get("status") or "failed")
        error_text = "" if ok else str(result.get("message") or result.get("error") or "")[:500]
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE data_mining_schedules
                SET last_run_key=?,
                    last_success_key=CASE WHEN ? THEN ? ELSE last_success_key END,
                    last_run_at=?,
                    last_success_at=CASE WHEN ? THEN ? ELSE last_success_at END,
                    last_status=?,
                    last_error=?,
                    last_file_name=CASE WHEN ? THEN ? ELSE last_file_name END,
                    last_file_path=CASE WHEN ? THEN ? ELSE last_file_path END,
                    updated_at=?
                WHERE schedule_id=?
                """,
                (
                    run_key,
                    int(ok),
                    run_key,
                    now,
                    int(ok),
                    now,
                    status_text[:50],
                    error_text,
                    int(ok),
                    str(result.get("file_name") or "")[:255],
                    int(ok),
                    str(result.get("file_path") or "")[:1000],
                    now,
                    schedule_id,
                ),
            )

    def list_data_mining_runs(self, schedule_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
        limit = min(max(int(limit or 50), 1), 200)
        query = "SELECT * FROM data_mining_runs"
        params: tuple[Any, ...] = ()
        if schedule_id:
            query += " WHERE schedule_id=?"
            params = (schedule_id,)
        query += " ORDER BY started_at DESC LIMIT ?"
        params = (*params, limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
            return [self._decode_data_mining_run(dict(row)) for row in rows]

    @staticmethod
    def _decode_connection(row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = json.loads(row.pop("config_json") or "{}")
        return row

    @staticmethod
    def _decode_sql_report(row: dict[str, Any]) -> dict[str, Any]:
        try:
            params = json.loads(row.get("cac_tham_so") or "[]")
        except json.JSONDecodeError:
            params = []
        row["cac_tham_so"] = params if isinstance(params, list) else []
        return row

    @staticmethod
    def _decode_dashboard_layout(row: dict[str, Any]) -> dict[str, Any]:
        try:
            layout = json.loads(row.pop("layout_json") or "{}")
        except json.JSONDecodeError:
            layout = {}
        row["layout"] = layout if isinstance(layout, dict) else {}
        return row

    @staticmethod
    def _decode_dashboard_chart_cache(row: dict[str, Any]) -> dict[str, Any]:
        for source_key, target_key in (("filters_json", "filters"), ("payload_json", "payload")):
            raw_value = row.pop(source_key, None)
            try:
                decoded = json.loads(raw_value or "{}")
            except json.JSONDecodeError:
                decoded = {}
            row[target_key] = decoded if isinstance(decoded, dict) else {}
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
        try:
            time_slots = json.loads(row.get("time_slots_json") or "[]")
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
        try:
            variables = json.loads(row.get("danh_sach_bien_json") or "[]")
        except json.JSONDecodeError:
            variables = []
        try:
            parameters = json.loads(row.get("parameters_json") or "{}")
        except json.JSONDecodeError:
            parameters = {}
        return {
            "id": row.get("id"),
            "ma_bao_cao": row.get("ma_bao_cao") or "",
            "ten_bao_cao": row.get("ten_bao_cao") or "",
            "danh_sach_bien": variables if isinstance(variables, list) else [],
            "parameters": parameters if isinstance(parameters, dict) else {},
            "report_url": row.get("report_url") or "",
            "storage_link": row.get("storage_link") or "",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _decode_onebss_report_run(row: dict[str, Any]) -> dict[str, Any]:
        try:
            parameters = json.loads(row.get("parameters_json") or "{}")
        except json.JSONDecodeError:
            parameters = {}
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
            "parameters": parameters if isinstance(parameters, dict) else {},
            "started_at": row.get("started_at") or "",
            "finished_at": row.get("finished_at") or "",
            "duration_ms": int(row.get("duration_ms") or 0),
            "created_by": row.get("created_by") or "",
        }

    @staticmethod
    def _decode_data_mining_schedule(row: dict[str, Any]) -> dict[str, Any]:
        try:
            parameters = json.loads(row.get("parameters_json") or "{}")
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
        try:
            parameters = json.loads(row.get("parameters_json") or "{}")
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

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")
