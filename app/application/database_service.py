import logging
from typing import Any

import httpx

from app.data_access.internal_api_client import InternalApiClient


logger = logging.getLogger(__name__)


class DatabaseService:
    """Xử lý nghiệp vụ lấy dữ liệu qua máy chủ FastAPI nội bộ."""

    def __init__(self, internal_api: InternalApiClient, app_repository: Any) -> None:
        self.internal_api = internal_api
        self.app_repository = app_repository

    def get_connection_status(self) -> dict[str, Any]:
        try:
            details = self.internal_api.health_check()
            return {
                "ok": True,
                "message": "Kết nối API dữ liệu nội bộ thành công.",
                "details": details,
            }
        except httpx.TimeoutException as error:
            logger.exception("Internal API timeout: %s", error)
            return {
                "ok": False,
                "message": "API dữ liệu nội bộ phản hồi quá lâu.",
                "details": {"error": str(error)},
            }
        except httpx.HTTPStatusError as error:
            logger.exception("Internal API status error: %s", error)
            return {
                "ok": False,
                "message": f"API dữ liệu nội bộ trả lỗi HTTP {error.response.status_code}.",
                "details": {"error": error.response.text[:300]},
            }
        except httpx.HTTPError as error:
            logger.exception("Cannot connect internal API: %s", error)
            return {
                "ok": False,
                "message": "Không kết nối được API dữ liệu nội bộ.",
                "details": {"error": str(error)},
            }

    def run_dynamic_report(
        self,
        *,
        ma_bao_cao: str,
        filters: dict[str, Any],
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        report = self.app_repository.get_sql_report_by_code(ma_bao_cao)
        if not report:
            return {
                "ok": False,
                "message": "Không tìm thấy cấu hình báo cáo.",
                "columns": [],
                "rows": [],
                "pagination": {"page": page, "page_size": page_size, "total": 0},
            }

        safe_page = max(1, page)
        safe_page_size = max(20, min(page_size, 50))
        allowed_params = set(report.get("cac_tham_so") or [])
        safe_filters = {key: value for key, value in filters.items() if key in allowed_params}

        try:
            result = self.internal_api.run_sql_report(
                ten_bao_cao=report["ten_bao_cao"],
                ma_bao_cao=report["ma_bao_cao"],
                cau_lenh_sql=report["cau_lenh_sql"],
                tham_so=safe_filters,
                page=safe_page,
                page_size=safe_page_size,
            )
        except httpx.TimeoutException as error:
            logger.exception("Dynamic report timeout: %s", error)
            return self._failed_report("API dữ liệu nội bộ phản hồi quá lâu.", safe_page, safe_page_size, str(error))
        except httpx.HTTPStatusError as error:
            logger.exception("Dynamic report HTTP error: %s", error)
            return self._failed_report(
                f"API dữ liệu nội bộ trả lỗi HTTP {error.response.status_code}.",
                safe_page,
                safe_page_size,
                error.response.text[:300],
            )
        except httpx.HTTPError as error:
            logger.exception("Dynamic report connection error: %s", error)
            return self._failed_report("Không kết nối được API dữ liệu nội bộ.", safe_page, safe_page_size, str(error))

        rows = result.get("rows") or result.get("data") or []
        if not isinstance(rows, list):
            rows = []

        columns = result.get("columns") or self._infer_columns(rows)
        total = int(result.get("total") or len(rows))

        return {
            "ok": bool(result.get("ok", True)),
            "message": result.get("message", "Đã tải dữ liệu báo cáo."),
            "report": {
                "ten_bao_cao": report["ten_bao_cao"],
                "ma_bao_cao": report["ma_bao_cao"],
                "cac_tham_so": report.get("cac_tham_so") or [],
            },
            "columns": columns,
            "rows": rows,
            "pagination": {
                "page": int(result.get("page") or safe_page),
                "page_size": int(result.get("page_size") or safe_page_size),
                "total": total,
            },
        }

    def run_dashboard_datcoc_test(self) -> dict[str, Any]:
        page = 1
        page_size = 20
        try:
            result = self.internal_api.run_sql_report(
                ten_bao_cao="Kiểm tra đặt cọc",
                ma_bao_cao="DASHBOARD_DATCOC_TEST",
                cau_lenh_sql="select * from css_cto.db_datcoc where ma_tb = 'thanhbinh-omon'",
                tham_so={},
                page=page,
                page_size=page_size,
            )
        except httpx.TimeoutException as error:
            logger.exception("Dashboard datcoc timeout: %s", error)
            return self._failed_report("API dữ liệu nội bộ phản hồi quá lâu.", page, page_size, str(error))
        except httpx.HTTPStatusError as error:
            logger.exception("Dashboard datcoc HTTP error: %s", error)
            return self._failed_report(
                f"API dữ liệu nội bộ trả lỗi HTTP {error.response.status_code}.",
                page,
                page_size,
                error.response.text[:300],
            )
        except httpx.HTTPError as error:
            logger.exception("Dashboard datcoc connection error: %s", error)
            return self._failed_report("Không kết nối được API dữ liệu nội bộ.", page, page_size, str(error))

        rows = result.get("rows") or result.get("data") or []
        if not isinstance(rows, list):
            rows = []
        columns = result.get("columns") or self._infer_columns(rows)

        return {
            "ok": bool(result.get("ok", True)),
            "message": result.get("message", "Đã tải dữ liệu đặt cọc."),
            "sql": "select * from css_cto.db_datcoc where ma_tb = 'thanhbinh-omon'",
            "columns": columns,
            "rows": rows,
            "pagination": {
                "page": int(result.get("page") or page),
                "page_size": int(result.get("page_size") or page_size),
                "total": int(result.get("total") or len(rows)),
            },
        }

    @staticmethod
    def _infer_columns(rows: list[Any]) -> list[str]:
        if rows and isinstance(rows[0], dict):
            return list(rows[0].keys())
        return []

    @staticmethod
    def _failed_report(message: str, page: int, page_size: int, detail: str) -> dict[str, Any]:
        return {
            "ok": False,
            "message": message,
            "details": {"error": detail},
            "columns": [],
            "rows": [],
            "pagination": {"page": page, "page_size": page_size, "total": 0},
        }
