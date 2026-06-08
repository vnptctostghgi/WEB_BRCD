from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import re
import threading
from typing import Any, Iterator

import oracledb

from app.settings import Settings


SELECT_STAR_PATTERN = re.compile(r"^\s*select\s+\*", re.IGNORECASE | re.DOTALL)
SELECT_PATTERN = re.compile(r"^\s*select\b", re.IGNORECASE)


class OraclePoolService:
    """Quan ly pool ket noi Oracle dung chung cho toan bo ung dung."""

    def __init__(self) -> None:
        self.settings: Settings | None = None
        self.pool: Any = None
        self.lock = threading.Lock()
        self.state = "not_started"
        self.last_error = ""
        self.last_checked_at: str | None = None

    def configure(self, settings: Settings) -> None:
        self.settings = settings

    def start(self) -> None:
        if not self.settings:
            raise RuntimeError("OraclePoolService chua duoc configure.")
        if self.settings.db_mock_mode:
            self.state = "mock"
            return
        if self.pool:
            return
        try:
            self._validate_configuration()
            dsn = oracledb.makedsn(
                self.settings.db_host,
                self.settings.db_port,
                service_name=self.settings.db_service,
            )
            with self.lock:
                self.pool = oracledb.create_pool(
                    user=self.settings.db_user,
                    password=self.settings.db_pass.get_secret_value(),
                    dsn=dsn,
                    min=self.settings.oracle_pool_min,
                    max=self.settings.oracle_pool_max,
                    increment=self.settings.oracle_pool_increment,
                    getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
                    wait_timeout=max(1, int(self.settings.oracle_connect_timeout_ms / 1000)),
                )
                self.state = "ready"
                self.last_error = ""
        except Exception as error:  # noqa: BLE001 - can bao cao trang thai thay vi lam sap app.
            self.pool = None
            self.state = "error"
            self.last_error = str(error)

    def stop(self) -> None:
        with self.lock:
            if self.pool:
                try:
                    self.pool.close(force=True)
                finally:
                    self.pool = None
                    self.state = "stopped"

    @contextmanager
    def acquire(self) -> Iterator[Any]:
        if not self.settings:
            raise RuntimeError("OraclePoolService chua duoc configure.")
        if self.settings.db_mock_mode:
            raise RuntimeError("Oracle dang o che do mock, khong co ket noi that.")
        if not self.pool:
            self.start()
        if not self.pool:
            raise RuntimeError(f"Oracle pool chua san sang: {self.last_error}")
        connection = self.pool.acquire()
        try:
            yield connection
        finally:
            self.pool.release(connection)

    def check_connection(self) -> dict[str, Any]:
        if not self.settings:
            raise RuntimeError("OraclePoolService chua duoc configure.")
        if self.settings.db_mock_mode:
            return {
                "database_time": datetime.now().isoformat(timespec="seconds"),
                "database_version": "Mock Oracle 0.1",
                "mode": "mock",
            }
        with self.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.call_timeout = self.settings.oracle_query_timeout_ms
                cursor.execute("SELECT SYSDATE AS SERVER_TIME FROM DUAL")
                database_time = cursor.fetchone()[0]
        self.last_checked_at = datetime.now().isoformat(timespec="seconds")
        return {
            "database_time": str(database_time),
            "database_version": connection.version,
            "mode": "oracle_pool",
        }

    def execute_paginated_select(
        self,
        sql: str,
        binds: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Thuc thi SELECT an toan: cam SELECT *, bat buoc phan trang tai DB."""
        if not self.settings:
            raise RuntimeError("OraclePoolService chua duoc configure.")
        safe_page_size = min(max(int(page_size), 1), 50)
        safe_page = max(int(page), 1)
        offset = (safe_page - 1) * safe_page_size
        clean_sql = self._validate_select_sql(sql)
        paginated_sql = f"{clean_sql} OFFSET :__offset ROWS FETCH NEXT :__limit ROWS ONLY"
        params = {**(binds or {}), "__offset": offset, "__limit": safe_page_size}
        with self.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.call_timeout = self.settings.oracle_query_timeout_ms
                cursor.execute(paginated_sql, params)
                columns = [column[0].lower() for column in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def status(self) -> dict[str, Any]:
        settings = self.settings
        pool = self.pool
        if settings and settings.db_mock_mode:
            return {
                "state": "mock",
                "mode": "mock",
                "pool_min": settings.oracle_pool_min,
                "pool_max": settings.oracle_pool_max,
                "busy": 0,
                "free": settings.oracle_pool_min,
                "opened": 0,
                "last_error": "",
                "last_checked_at": self.last_checked_at,
            }
        opened = int(getattr(pool, "opened", 0) or 0) if pool else 0
        busy = int(getattr(pool, "busy", 0) or 0) if pool else 0
        pool_min = settings.oracle_pool_min if settings else 0
        pool_max = settings.oracle_pool_max if settings else 0
        return {
            "state": self.state,
            "mode": "oracle_pool" if pool else "not_ready",
            "pool_min": pool_min,
            "pool_max": pool_max,
            "busy": busy,
            "free": max(opened - busy, 0),
            "opened": opened,
            "connect_timeout_ms": settings.oracle_connect_timeout_ms if settings else 0,
            "query_timeout_ms": settings.oracle_query_timeout_ms if settings else 0,
            "last_error": self.last_error,
            "last_checked_at": self.last_checked_at,
        }

    def _validate_configuration(self) -> None:
        assert self.settings is not None
        required_values = {
            "DB_HOST": self.settings.db_host,
            "DB_SERVICE": self.settings.db_service,
            "DB_USER": self.settings.db_user,
            "DB_PASS": self.settings.db_pass.get_secret_value(),
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise ValueError(f"Thieu cau hinh: {', '.join(missing)}")

    @staticmethod
    def _validate_select_sql(sql: str) -> str:
        clean_sql = (sql or "").strip().rstrip(";")
        if not SELECT_PATTERN.match(clean_sql):
            raise ValueError("Chi cho phep cau lenh SELECT.")
        if SELECT_STAR_PATTERN.match(clean_sql):
            raise ValueError("Khong duoc dung SELECT *. Hay chi ro cac cot can lay.")
        if re.search(r"\b(offset|fetch\s+next|limit)\b", clean_sql, re.IGNORECASE):
            raise ValueError("Khong tu chen phan trang trong SQL dau vao. He thong se tu phan trang.")
        return clean_sql


oracle_pool_service = OraclePoolService()
