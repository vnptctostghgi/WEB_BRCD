import logging
import json
import re
from datetime import datetime
from typing import Any

import httpx

from app.data_access.internal_api_client import InternalApiClient


logger = logging.getLogger(__name__)


DEFINE_PATTERN = re.compile(r"^\s*define\s+([A-Za-z][A-Za-z0-9_$#]*)\s*=\s*(.+?)\s*$", re.IGNORECASE)


class DatabaseService:
    """Xử lý nghiệp vụ lấy dữ liệu qua máy chủ FastAPI nội bộ."""

    FIBER_LOAIHINH_ID = "58"
    FIBER_KIEULD_IDS = (
        51, 321, 13121, 11000, 11001, 685, 194, 196, 570, 614,
        14015, 26, 643, 644, 722, 733,
    )

    def __init__(self, internal_api: InternalApiClient, app_repository: Any) -> None:
        self.internal_api = internal_api
        self.app_repository = app_repository

    @staticmethod
    def _normalized_report_code(value: Any) -> str:
        text = str(value or "").strip()
        return text.upper() if re.fullmatch(r"[A-Za-z0-9_-]+", text) else ""

    def _find_sql_report(self, ma_bao_cao: str, report_id: Any = None, report_name: Any = None) -> dict[str, Any] | None:
        if report_id not in (None, ""):
            try:
                report = self.app_repository.get_sql_report_by_id(int(report_id))
                if report:
                    return report
            except (TypeError, ValueError):
                pass
        target_code = self._normalized_report_code(ma_bao_cao)
        report = self.app_repository.get_sql_report_by_code(target_code or ma_bao_cao)
        if report:
            return report
        target_name = str(report_name or "").strip().casefold()
        if not target_code and not target_name:
            return None
        for item in self.app_repository.list_sql_reports():
            if self._normalized_report_code(item.get("ma_bao_cao")) == target_code:
                return item
            if self._normalized_report_code(item.get("ten_bao_cao")) == target_code:
                return item
            if target_name and str(item.get("ten_bao_cao") or "").strip().casefold() == target_name:
                return item
        return None

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
        report_id: Any = None,
        report_name: Any = None,
    ) -> dict[str, Any]:
        report = self._find_sql_report(ma_bao_cao, report_id=report_id, report_name=report_name)
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
        allowed_params = [str(param).strip().lstrip(":") for param in (report.get("cac_tham_so") or []) if str(param).strip()]
        allowed_param_by_upper = {param.upper(): param for param in allowed_params}
        safe_filters: dict[str, Any] = {}
        ignored_filters: list[str] = []
        for key, value in (filters or {}).items():
            normalized_key = str(key).strip().lstrip(":").upper()
            if not normalized_key:
                continue
            if allowed_param_by_upper:
                target_key = allowed_param_by_upper.get(normalized_key)
                if not target_key:
                    ignored_filters.append(str(key))
                    continue
                safe_filters[target_key] = value
            else:
                safe_filters[str(key).strip().lstrip(":")] = value
        compiled_sql, define_details = self._compile_define_sql(report["cau_lenh_sql"], safe_filters)
        executable_filters = self._filters_for_compiled_sql(compiled_sql, safe_filters)

        safe_report_code = (
            self._normalized_report_code(report.get("ma_bao_cao"))
            or self._normalized_report_code(report.get("ten_bao_cao"))
            or self._normalized_report_code(ma_bao_cao)
            or str(report.get("ma_bao_cao") or ma_bao_cao).strip()
        )

        try:
            result = self.internal_api.run_sql_report(
                ten_bao_cao=report["ten_bao_cao"],
                ma_bao_cao=safe_report_code,
                cau_lenh_sql=compiled_sql,
                tham_so=executable_filters,
                page=safe_page,
                page_size=safe_page_size,
            )
        except httpx.TimeoutException as error:
            logger.exception("Dynamic report timeout: %s", error)
            return self._failed_report("API dữ liệu nội bộ phản hồi quá lâu.", safe_page, safe_page_size, str(error), compiled_sql, executable_filters, define_details)
        except httpx.HTTPStatusError as error:
            logger.exception("Dynamic report HTTP error: %s", error)
            return self._failed_report(
                f"API dữ liệu nội bộ trả lỗi HTTP {error.response.status_code}.",
                safe_page,
                safe_page_size,
                error.response.text[:300],
                compiled_sql,
                executable_filters,
                define_details,
            )
        except httpx.HTTPError as error:
            logger.exception("Dynamic report connection error: %s", error)
            return self._failed_report("Không kết nối được API dữ liệu nội bộ.", safe_page, safe_page_size, str(error), compiled_sql, executable_filters, define_details)

        rows = result.get("rows") or result.get("data") or []
        if not isinstance(rows, list):
            rows = []

        columns = result.get("columns") or self._infer_columns(rows)
        total = int(result.get("total") or len(rows))
        details = result.get("details") if isinstance(result.get("details"), dict) else {}
        if ignored_filters:
            details = {**details, "ignored_filters": ignored_filters, "allowed_params": allowed_params}
        if define_details:
            details = {**details, **define_details}
        if define_details:
            details = {**details, "sent_params": executable_filters}

        return {
            "ok": bool(result.get("ok", True)),
            "message": result.get("message", "Đã tải dữ liệu báo cáo."),
            "details": details,
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

    @classmethod
    def _compile_define_sql(cls, sql: str, filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        normalized = sql.strip()
        body = normalized[:-1].strip() if normalized.endswith(";") else normalized
        lines = body.splitlines()
        definitions: dict[str, str] = {}
        select_lines: list[str] = []
        in_select = False
        for line in lines:
            match = DEFINE_PATTERN.match(line)
            if match and not in_select:
                name, expression = match.groups()
                definitions[name] = cls._define_value(expression, filters)
                continue
            if line.strip():
                in_select = True
            if in_select:
                select_lines.append(line)
        compiled = "\n".join(select_lines).strip()
        for name, value in definitions.items():
            compiled = re.sub(rf"&{re.escape(name)}\b", cls._escape_define_value(value), compiled, flags=re.IGNORECASE)
        details = {"define_params": list(definitions)} if definitions else {}
        return compiled, details

    @staticmethod
    def _define_value(expression: str, filters: dict[str, Any]) -> str:
        value = expression.strip()
        if value.startswith(":"):
            filter_name = value[1:].strip().upper()
            filters_by_upper = {str(key).strip().lstrip(":").upper(): item for key, item in filters.items()}
            value = str(filters_by_upper.get(filter_name, ""))
        return value.strip().strip("'\"")

    @staticmethod
    def _escape_define_value(value: str) -> str:
        return str(value).replace("'", "''")

    @staticmethod
    def _filters_for_compiled_sql(sql: str, filters: dict[str, Any]) -> dict[str, Any]:
        bind_names = {match.upper() for match in re.findall(r":([A-Za-z][A-Za-z0-9_$#]*)", sql)}
        if not bind_names:
            return {}
        return {
            key: value
            for key, value in filters.items()
            if str(key).strip().lstrip(":").upper() in bind_names
        }

    @staticmethod
    def _dashboard_widget_query_key(sql_code: str, filters: dict[str, Any], report_id: Any = None) -> str:
        normalized_filters = json.dumps(filters or {}, ensure_ascii=False, sort_keys=True, default=str)
        return f"{report_id or ''}|{sql_code}|{normalized_filters}"

    def run_dashboard_layout_tab(self, *, page_id: str, tab_id: str) -> dict[str, Any]:
        layout_row = self.app_repository.get_dashboard_layout(page_id)
        if not layout_row:
            return {
                "ok": False,
                "message": "Không tìm thấy trang dashboard.",
                "page_id": page_id,
                "tab_id": tab_id,
                "widgets": [],
            }

        layout = layout_row.get("layout") or {}
        tabs = layout.get("tabs") if isinstance(layout.get("tabs"), list) else []
        tab = next((item for item in tabs if str(item.get("tab_id")) == tab_id), None)
        if not tab:
            return {
                "ok": False,
                "message": "Không tìm thấy Tab dashboard.",
                "page_id": page_id,
                "tab_id": tab_id,
                "widgets": [],
            }

        widget_results = []
        data_cache: dict[str, dict[str, Any]] = {}
        all_ok = True
        for row in tab.get("grid_layout") or []:
            row_id = row.get("row_id")
            for widget in row.get("widgets") or []:
                sql_code = str(widget.get("sql_code") or "").strip().upper()
                if not sql_code:
                    continue
                filters = widget.get("filters") if isinstance(widget.get("filters"), dict) else {}
                cache_key = self._dashboard_widget_query_key(sql_code, filters, widget.get("report_id"))
                if cache_key not in data_cache:
                    data_cache[cache_key] = self.run_dynamic_report(
                        ma_bao_cao=sql_code,
                        filters=filters,
                        page=1,
                        page_size=20,
                        report_id=widget.get("report_id"),
                        report_name=widget.get("title"),
                    )
                result = data_cache[cache_key]
                all_ok = all_ok and bool(result.get("ok"))
                widget_results.append({
                    "row_id": row_id,
                    "position": widget.get("position"),
                    "type": widget.get("type"),
                    "title": widget.get("title") or sql_code,
                    "sql_code": sql_code,
                    "data": result,
                })

        failed_widgets = [
            {
                "row_id": item.get("row_id"),
                "position": item.get("position"),
                "title": item.get("title"),
                "sql_code": item.get("sql_code"),
                "message": (item.get("data") or {}).get("message"),
                "details": (item.get("data") or {}).get("details"),
            }
            for item in widget_results
            if not bool((item.get("data") or {}).get("ok"))
        ]

        return {
            "ok": all_ok,
            "message": "Đã tải dữ liệu Tab dashboard." if all_ok else "Một số biểu đồ chưa tải được dữ liệu.",
            "page_id": page_id,
            "tab_id": tab_id,
            "widgets": widget_results,
            "failed_widgets": failed_widgets,
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
    def _failed_report(
        message: str,
        page: int,
        page_size: int,
        detail: str,
        compiled_sql: str | None = None,
        sent_params: dict[str, Any] | None = None,
        extra_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        details = {"error": detail}
        if compiled_sql is not None:
            details["compiled_sql_preview"] = compiled_sql[:1200]
        if sent_params is not None:
            details["sent_params"] = sent_params
        if extra_details:
            details.update(extra_details)
        return {
            "ok": False,
            "message": message,
            "details": details,
            "columns": [],
            "rows": [],
            "pagination": {"page": page, "page_size": page_size, "total": 0},
        }

    def run_dashboard_fiber(self) -> dict[str, Any]:
        period_label = datetime.now().strftime("%m/%Y")
        vnpt = self._run_dashboard_fiber_group(
            unit_prefix="VNPT",
            ma_bao_cao="DASHBOARD_FIBER_VNPT",
            ten_bao_cao="Sản lượng Fiber VNPT Khu vực",
        )
        ttvt = self._run_dashboard_fiber_group(
            unit_prefix="TTVT",
            ma_bao_cao="DASHBOARD_FIBER_TTVT",
            ten_bao_cao="Sản lượng Fiber TTVT Khu vực",
        )
        ok = bool(vnpt["ok"] and ttvt["ok"])
        return {
            "ok": ok,
            "message": "Đã tải dữ liệu Fiber." if ok else "Một phần dữ liệu Fiber chưa tải được.",
            "period_label": period_label,
            "summary": {
                "production": {
                    "fiber": vnpt["total"],
                    "mytv": None,
                    "mesh": None,
                    "cam": None,
                },
                "revenue": {
                    "total": None,
                    "fiber": None,
                    "mytv": None,
                    "mesh": None,
                    "cam": None,
                },
            },
            "groups": {
                "vnpt": vnpt,
                "ttvt": ttvt,
            },
        }

    def _run_dashboard_fiber_group(self, *, unit_prefix: str, ma_bao_cao: str, ten_bao_cao: str) -> dict[str, Any]:
        page = 1
        page_size = 50
        sql = self._dashboard_fiber_sql(unit_prefix)
        try:
            result = self.internal_api.run_sql_report(
                ten_bao_cao=ten_bao_cao,
                ma_bao_cao=ma_bao_cao,
                cau_lenh_sql=sql,
                tham_so={},
                page=page,
                page_size=page_size,
            )
        except httpx.TimeoutException as error:
            logger.exception("Dashboard fiber timeout: %s", error)
            return self._failed_fiber_group("API dữ liệu nội bộ phản hồi quá lâu.", str(error))
        except httpx.HTTPStatusError as error:
            logger.exception("Dashboard fiber HTTP error: %s", error)
            return self._failed_fiber_group(
                f"API dữ liệu nội bộ trả lỗi HTTP {error.response.status_code}.",
                error.response.text[:300],
            )
        except httpx.HTTPError as error:
            logger.exception("Dashboard fiber connection error: %s", error)
            return self._failed_fiber_group("Không kết nối được API dữ liệu nội bộ.", str(error))

        rows = result.get("rows") or result.get("data") or []
        if not isinstance(rows, list):
            rows = []
        normalized_rows = self._normalize_fiber_rows(rows)
        return {
            "ok": bool(result.get("ok", True)),
            "message": result.get("message", "Đã tải dữ liệu Fiber."),
            "rows": normalized_rows,
            "total": sum(row["fiber_quantity"] for row in normalized_rows),
        }

    def _dashboard_fiber_sql(self, unit_prefix: str) -> str:
        safe_prefix = unit_prefix.replace("'", "''")
        kieuld_ids = ", ".join(str(item) for item in self.FIBER_KIEULD_IDS)
        return f"""
SELECT
    nv.ten_donvi_cha,
    COUNT(dbtb.ma_tb) AS so_luong_thuebao
FROM
    css_cto.db_thuebao dbtb,
    css_cto.hd_thuebao hdtb,
    css_cto.hd_khachhang hdkh,
    v_nhanvien nv,
    css_cto.kieu_ld ld,
    css_cto.dbtb_kv dbkv
WHERE
    dbtb.loaitb_id = '{self.FIBER_LOAIHINH_ID}'
    AND dbtb.ngay_sd >= TRUNC(SYSDATE, 'MM')
    AND dbtb.ngay_sd <= LAST_DAY(SYSDATE)
    AND dbtb.ngay_cat IS NULL
    AND dbtb.phanvung_id = hdtb.phanvung_id
    AND dbtb.thuebao_id = hdtb.thuebao_id
    AND hdtb.ngay_ht >= TRUNC(SYSDATE, 'MM')
    AND hdtb.ngay_ht <= LAST_DAY(SYSDATE)
    AND hdtb.tthd_id = 6
    AND hdtb.phanvung_id = hdkh.phanvung_id
    AND hdtb.hdkh_id = hdkh.hdkh_id
    AND hdkh.phanvung_id = nv.phanvung_id
    AND NVL(hdkh.ctv_id, NVL(hdkh.nhanviengt_id, hdkh.nhanvien_id)) = nv.nhanvien_id
    AND hdtb.phanvung_id = dbkv.phanvung_id
    AND hdtb.thuebao_id = dbkv.thuebao_id
    AND dbkv.khuvuc_id = nv.khuvuc_id
    AND hdtb.kieuld_id = ld.kieuld_id
    AND ld.kieuld_id IN ({kieuld_ids})
    AND nv.ten_donvi_cha LIKE '{safe_prefix}%'
GROUP BY
    nv.ten_donvi_cha
ORDER BY
    so_luong_thuebao DESC
""".strip()

    @classmethod
    def _normalize_fiber_rows(cls, rows: list[Any]) -> list[dict[str, Any]]:
        normalized_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            unit_name = str(cls._row_value(row, "unit_name", "ten_donvi_cha", "TEN_DONVI_CHA") or "").strip()
            quantity = cls._to_int(cls._row_value(row, "fiber_quantity", "so_luong_thuebao", "SO_LUONG_THUEBAO"))
            if not unit_name:
                continue
            normalized_rows.append({"unit_name": unit_name, "fiber_quantity": quantity})
        normalized_rows.sort(key=lambda item: item["fiber_quantity"], reverse=True)
        return [
            {"rank": index + 1, **row}
            for index, row in enumerate(normalized_rows[:13])
        ]

    @staticmethod
    def _row_value(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row:
                return row[key]
        lower_key_map = {str(key).lower(): key for key in row}
        for key in keys:
            actual_key = lower_key_map.get(key.lower())
            if actual_key is not None:
                return row[actual_key]
        return None

    @staticmethod
    def _to_int(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        cleaned = str(value).strip().replace(".", "").replace(",", "")
        try:
            return int(cleaned)
        except ValueError:
            return 0

    @staticmethod
    def _failed_fiber_group(message: str, detail: str) -> dict[str, Any]:
        return {
            "ok": False,
            "message": message,
            "details": {"error": detail},
            "rows": [],
            "total": 0,
        }
