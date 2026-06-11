from __future__ import annotations

from typing import Any

import httpx

from app.settings import Settings


class InternalApiClient:
    """Client gọi máy chủ FastAPI nội bộ để lấy dữ liệu từ DB cơ quan."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_url = settings.internal_api_url
        self.timeout = settings.internal_api_timeout_seconds

    def health_check(self) -> dict[str, Any]:
        if self.settings.internal_api_mock_mode:
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
    ) -> dict[str, Any]:
        if self.settings.internal_api_mock_mode:
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
            }
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        token = self.settings.internal_api_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            return {"ok": True, "data": data}
        return data
