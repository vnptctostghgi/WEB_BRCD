from __future__ import annotations

from typing import Any

import httpx

from app.settings import Settings


class InternalApiClient:
    """Client gọi máy chủ FastAPI nội bộ để lấy dữ liệu từ DB cơ quan."""

    def __init__(self, settings: Settings, connection: dict[str, Any] | None = None) -> None:
        self.settings = settings
        config = connection.get("config") if isinstance(connection, dict) else {}
        config = config if isinstance(config, dict) else {}
        use_connection = (
            isinstance(connection, dict)
            and connection.get("connection_type") == "internal_api"
            and bool(connection.get("is_active"))
        )
        self.api_url = (
            str(config.get("url") or config.get("api_url") or settings.internal_api_url).strip()
            if use_connection
            else settings.internal_api_url
        )
        self.mock_mode = self._bool_config(config.get("mock_mode"), settings.internal_api_mock_mode) if use_connection else settings.internal_api_mock_mode
        token = str(config.get("token") or "").strip() if use_connection else ""
        self.token = token or settings.internal_api_token.get_secret_value()
        self.timeout = settings.internal_api_timeout_seconds

    @classmethod
    def from_repository(cls, settings: Settings, repository: Any) -> "InternalApiClient":
        connection = None
        if hasattr(repository, "get_system_connection_by_code"):
            try:
                connection = repository.get_system_connection_by_code("internal_fastapi_api")
            except Exception:
                connection = None
        return cls(settings, connection)

    @staticmethod
    def _bool_config(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return default

    def health_check(self) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "ok": True,
                "mode": "mock",
                "message": "Đang chạy chế độ thử nghiệm, chưa gọi API nội bộ.",
                "api_url": self.api_url,
            }

        return self._post(
            {
                "action": "health_check",
                "source": "vnptcto-web",
            }
        )

    def run_sql_report(
        self,
        *,
        ten_bao_cao: str,
        ma_bao_cao: str,
        cau_lenh_sql: str,
        tham_so: dict[str, Any],
        page: int,
        page_size: int,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        if self.mock_mode:
            if ma_bao_cao in {"DASHBOARD_FIBER_VNPT", "DASHBOARD_FIBER_TTVT"}:
                rows = self._mock_fiber_rows(ma_bao_cao)
                return {
                    "ok": True,
                    "mode": "mock",
                    "columns": ["ten_donvi_cha", "so_luong_thuebao"],
                    "rows": rows,
                    "total": len(rows),
                    "page": page,
                    "page_size": page_size,
                    "message": "Dữ liệu mẫu Fiber. Tắt INTERNAL_API_MOCK_MODE để gọi API nội bộ thật.",
                }
            rows = [
                {
                    "STT": ((page - 1) * page_size) + index + 1,
                    "MA_BAO_CAO": ma_bao_cao,
                    "TEN_BAO_CAO": ten_bao_cao,
                    "THAM_SO": ", ".join(f"{key}={value}" for key, value in tham_so.items()) or "Không có",
                }
                for index in range(min(page_size, 3))
            ]
            return {
                "ok": True,
                "mode": "mock",
                "columns": ["STT", "MA_BAO_CAO", "TEN_BAO_CAO", "THAM_SO"],
                "rows": rows,
                "total": len(rows),
                "page": page,
                "page_size": page_size,
                "message": "Dữ liệu mẫu. Tắt INTERNAL_API_MOCK_MODE để gọi API nội bộ thật.",
            }

        return self._post(
            {
                "action": "run_sql_report",
                "ten_bao_cao": ten_bao_cao,
                "ma_bao_cao": ma_bao_cao,
                "cau_lenh_sql": cau_lenh_sql,
                "tham_so": tham_so,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                },
            },
            timeout=timeout,
        )

    def export_sql_report_to_drive(
        self,
        *,
        ten_bao_cao: str,
        ma_bao_cao: str,
        cau_lenh_sql: str,
        tham_so: dict[str, Any],
        drive_folder_id: str,
        file_name: str,
        page_size: int,
        max_rows: int,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "ok": False,
                "status": "mock_mode",
                "message": "API dữ liệu nội bộ đang ở chế độ mock, chưa thể xuất file trên máy trạm.",
            }

        return self._post(
            {
                "action": "export_sql_report_to_drive",
                "ten_bao_cao": ten_bao_cao,
                "ma_bao_cao": ma_bao_cao,
                "cau_lenh_sql": cau_lenh_sql,
                "tham_so": tham_so,
                "drive_folder_id": drive_folder_id,
                "file_name": file_name,
                "pagination": {
                    "page_size": page_size,
                    "max_rows": max_rows,
                },
            },
            timeout=timeout,
        )

    @staticmethod
    def _mock_fiber_rows(ma_bao_cao: str) -> list[dict[str, Any]]:
        prefix = "VNPT" if ma_bao_cao == "DASHBOARD_FIBER_VNPT" else "TTVT"
        return [
            {"ten_donvi_cha": f"{prefix} Khu vực {index:02d}", "so_luong_thuebao": 140 - (index * 7)}
            for index in range(1, 14)
        ]

    def _post(self, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        token = self.token
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with httpx.Client(timeout=timeout or self.timeout) as client:
            response = client.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            return {"ok": True, "data": data}
        return data
