import logging
import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.data_access.internal_api_client import InternalApiClient


logger = logging.getLogger(__name__)


DEFINE_PATTERN = re.compile(r"^\s*define\s+([A-Za-z][A-Za-z0-9_$#]*)\s*=\s*(.+?)\s*$", re.IGNORECASE)
IN_LIST_BIND_PATTERN = re.compile(r"\bin\s*\(\s*:([A-Za-z][A-Za-z0-9_$#]*)\s*\)", re.IGNORECASE)
REPORT_NOT_PROVIDED = object()


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
                "message": self._internal_api_connection_message(error),
                "details": {"error": str(error)},
            }

    def run_dynamic_report(
        self,
        *,
        ma_bao_cao: str,
        filters: dict[str, Any],
        page: int,
        page_size: int,
        search: str = "",
        search_columns: list[str] | None = None,
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
        safe_page_size = 10 if page_size <= 10 else 20
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
        compiled_sql, bind_filters = self._expand_in_list_bind_params(compiled_sql, safe_filters)
        executable_filters = self._filters_for_compiled_sql(compiled_sql, bind_filters)

        safe_report_code = (
            self._normalized_report_code(report.get("ma_bao_cao"))
            or self._normalized_report_code(report.get("ten_bao_cao"))
            or self._normalized_report_code(ma_bao_cao)
            or str(report.get("ma_bao_cao") or ma_bao_cao).strip()
        )
        search_text = str(search or "").strip()

        if search_text:
            compiled_sql, executable_filters = self._wrap_sql_for_search(
                compiled_sql,
                executable_filters,
                search_columns or [],
                search_text,
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
            return self._failed_report(self._internal_api_connection_message(error), safe_page, safe_page_size, str(error), compiled_sql, executable_filters, define_details)

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

    def export_dynamic_report(
        self,
        *,
        ma_bao_cao: str,
        filters: dict[str, Any],
        search: str = "",
        search_columns: list[str] | None = None,
        report_id: Any = None,
        report_name: Any = None,
        progress_callback: Any | None = None,
        page_callback: Any | None = None,
        collect_rows: bool = True,
    ) -> dict[str, Any]:
        report = self._find_sql_report(ma_bao_cao, report_id=report_id, report_name=report_name)
        fetch_page_size = self._dynamic_report_export_page_size()
        if not report:
            return self._failed_report("Không tìm thấy cấu hình báo cáo.", 1, fetch_page_size, "")

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
        compiled_sql, bind_filters = self._expand_in_list_bind_params(compiled_sql, safe_filters)
        executable_filters = self._filters_for_compiled_sql(compiled_sql, bind_filters)
        safe_report_code = (
            self._normalized_report_code(report.get("ma_bao_cao"))
            or self._normalized_report_code(report.get("ten_bao_cao"))
            or self._normalized_report_code(ma_bao_cao)
            or str(report.get("ma_bao_cao") or ma_bao_cao).strip()
        )
        search_text = str(search or "").strip()
        if search_text:
            compiled_sql, executable_filters = self._wrap_sql_for_search(
                compiled_sql,
                executable_filters,
                search_columns or [],
                search_text,
            )

        try:
            export_max_rows = self._dynamic_report_export_max_rows()
            fetched = self._fetch_dynamic_report_rows(
                ten_bao_cao=report["ten_bao_cao"],
                ma_bao_cao=safe_report_code,
                cau_lenh_sql=compiled_sql,
                tham_so=executable_filters,
                max_rows=export_max_rows,
                timeout=self._dynamic_report_export_timeout_seconds(),
                progress_callback=progress_callback,
                page_callback=page_callback,
                collect_rows=collect_rows,
                page_size=fetch_page_size,
            )
        except httpx.TimeoutException as error:
            logger.exception("Dynamic report export timeout: %s", error)
            return self._failed_report("API dữ liệu nội bộ phản hồi quá lâu.", 1, fetch_page_size, str(error), compiled_sql, executable_filters, define_details)
        except httpx.HTTPStatusError as error:
            logger.exception("Dynamic report export HTTP error: %s", error)
            return self._failed_report(
                f"API dữ liệu nội bộ trả lỗi HTTP {error.response.status_code}.",
                1,
                fetch_page_size,
                error.response.text[:300],
                compiled_sql,
                executable_filters,
                define_details,
            )
        except httpx.HTTPError as error:
            logger.exception("Dynamic report export connection error: %s", error)
            return self._failed_report(self._internal_api_connection_message(error), 1, fetch_page_size, str(error), compiled_sql, executable_filters, define_details)
        except RuntimeError as error:
            logger.exception("Dynamic report export API error: %s", error)
            return self._failed_report("API dữ liệu nội bộ trả lỗi khi chạy báo cáo.", 1, fetch_page_size, str(error), compiled_sql, executable_filters, define_details)

        rows = fetched["rows"]
        exported_rows = int(fetched.get("fetched_rows") or len(rows))
        details = {
            "search": search_text,
            "fetched_total": fetched["fetched_total"],
            "fetched_rows": exported_rows,
            "export_rows": exported_rows,
            "export_max_rows": export_max_rows,
            "truncated": fetched["truncated"],
        }
        if ignored_filters:
            details = {**details, "ignored_filters": ignored_filters, "allowed_params": allowed_params}
        if define_details:
            details = {**details, **define_details, "sent_params": executable_filters}
        if fetched["truncated"]:
            return self._failed_report(
                self._truncated_export_message(fetched["fetched_total"], export_max_rows),
                1,
                fetch_page_size,
                f"Export stopped at {exported_rows} rows.",
                compiled_sql,
                executable_filters,
                details,
            )

        return {
            "ok": True,
            "message": f"Đã chuẩn bị {exported_rows} dòng để xuất Excel.",
            "details": details,
            "report": {
                "ten_bao_cao": report["ten_bao_cao"],
                "ma_bao_cao": report["ma_bao_cao"],
                "cac_tham_so": report.get("cac_tham_so") or [],
            },
            "columns": fetched["columns"],
            "rows": rows,
            "pagination": {"page": 1, "page_size": exported_rows, "total": exported_rows},
        }

    def export_dynamic_report_to_drive(
        self,
        *,
        ma_bao_cao: str,
        filters: dict[str, Any],
        drive_folder_id: str,
        file_name: str,
        search: str = "",
        search_columns: list[str] | None = None,
    ) -> dict[str, Any]:
        report = self._find_sql_report(ma_bao_cao)
        fetch_page_size = self._dynamic_report_export_page_size()
        if not report:
            return self._failed_report("Không tìm thấy cấu hình báo cáo.", 1, fetch_page_size, "")

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
        compiled_sql, bind_filters = self._expand_in_list_bind_params(compiled_sql, safe_filters)
        executable_filters = self._filters_for_compiled_sql(compiled_sql, bind_filters)
        search_text = str(search or "").strip()
        if search_text:
            try:
                compiled_sql, executable_filters = self._wrap_sql_for_search(
                    compiled_sql,
                    executable_filters,
                    search_columns or [],
                    search_text,
                )
            except RuntimeError as error:
                return self._failed_report(str(error), 1, fetch_page_size, "", compiled_sql, executable_filters, define_details)

        safe_report_code = (
            self._normalized_report_code(report.get("ma_bao_cao"))
            or self._normalized_report_code(report.get("ten_bao_cao"))
            or self._normalized_report_code(ma_bao_cao)
            or str(report.get("ma_bao_cao") or ma_bao_cao).strip()
        )
        try:
            result = self.internal_api.export_sql_report_to_drive(
                ten_bao_cao=report["ten_bao_cao"],
                ma_bao_cao=safe_report_code,
                cau_lenh_sql=compiled_sql,
                tham_so=executable_filters,
                drive_folder_id=drive_folder_id,
                file_name=file_name,
                page_size=fetch_page_size,
                max_rows=self._dynamic_report_export_max_rows(),
                timeout=self._dynamic_report_export_timeout_seconds(),
            )
        except httpx.TimeoutException as error:
            logger.exception("Remote dynamic report export timeout: %s", error)
            return self._failed_report("Máy trạm xuất Excel phản hồi quá lâu.", 1, fetch_page_size, str(error), compiled_sql, executable_filters, define_details)
        except httpx.HTTPStatusError as error:
            logger.exception("Remote dynamic report export HTTP error: %s", error)
            return self._failed_report(
                f"Máy trạm chưa xuất được Excel lên Drive, HTTP {error.response.status_code}.",
                1,
                fetch_page_size,
                error.response.text[:300],
                compiled_sql,
                executable_filters,
                define_details,
            )
        except httpx.HTTPError as error:
            logger.exception("Remote dynamic report export connection error: %s", error)
            return self._failed_report(self._internal_api_connection_message(error), 1, fetch_page_size, str(error), compiled_sql, executable_filters, define_details)

        if not isinstance(result, dict):
            result = {"ok": False, "message": "Máy trạm trả phản hồi xuất Excel không hợp lệ."}
        if ignored_filters:
            result["ignored_filters"] = ignored_filters
        if define_details:
            result["define_details"] = define_details
        result.setdefault("report", {"ten_bao_cao": report["ten_bao_cao"], "ma_bao_cao": report["ma_bao_cao"]})
        return result

    @classmethod
    def _wrap_sql_for_search(
        cls,
        sql: str,
        filters: dict[str, Any],
        search_columns: list[str],
        search: str,
    ) -> tuple[str, dict[str, Any]]:
        columns = [str(column).strip() for column in search_columns if str(column).strip()]
        if not columns:
            raise RuntimeError("Chưa có danh sách cột để tìm kiếm. Hãy bấm Lấy dữ liệu trước, sau đó bấm Tìm.")

        terms = [term for term in re.split(r"\s+", str(search or "").casefold().strip()) if term]
        if not terms:
            return sql, filters

        wrapped_filters = dict(filters)
        term_clauses: list[str] = []
        for term_index, term in enumerate(terms, start=1):
            bind_name = f"SEARCH_TERM_{term_index}"
            wrapped_filters[bind_name] = f"%{term}%"
            column_clauses = [
                f"LOWER(TO_CHAR(Q.{cls._quote_oracle_identifier(column)})) LIKE :{bind_name}"
                for column in columns
            ]
            term_clauses.append("(" + " OR ".join(column_clauses) + ")")

        clean_sql = sql.strip()
        while clean_sql.endswith(";"):
            clean_sql = clean_sql[:-1].strip()
        return f"SELECT * FROM ({clean_sql}) Q WHERE {' AND '.join(term_clauses)}", wrapped_filters

    @staticmethod
    def _quote_oracle_identifier(identifier: str) -> str:
        return '"' + str(identifier).replace('"', '""') + '"'

    def _dynamic_report_fetch_page_size(self) -> int:
        settings = getattr(self.internal_api, "settings", None)
        configured = int(getattr(settings, "dynamic_report_fetch_page_size", 500) or 500)
        return max(20, min(configured, 1000))

    def _dynamic_report_export_page_size(self) -> int:
        settings = getattr(self.internal_api, "settings", None)
        configured = int(getattr(settings, "dynamic_report_export_page_size", 5000) or 5000)
        return max(1000, min(configured, 20000))

    def _dynamic_report_export_max_rows(self) -> int:
        settings = getattr(self.internal_api, "settings", None)
        configured = int(getattr(settings, "dynamic_report_export_max_rows", 1000000) or 1000000)
        return max(1, configured)

    def _dynamic_report_export_timeout_seconds(self) -> int:
        settings = getattr(self.internal_api, "settings", None)
        configured = int(getattr(settings, "dynamic_report_export_timeout_seconds", 180) or 180)
        return max(20, configured)

    @staticmethod
    def _truncated_export_message(fetched_total: int, max_rows: int) -> str:
        if fetched_total and fetched_total > max_rows:
            return f"Dữ liệu có {fetched_total:,} dòng, vượt giới hạn xuất hiện tại {max_rows:,} dòng. Tăng DYNAMIC_REPORT_EXPORT_MAX_ROWS để xuất đủ 100%."
        return f"Dữ liệu vượt giới hạn xuất hiện tại {max_rows:,} dòng. Tăng DYNAMIC_REPORT_EXPORT_MAX_ROWS để xuất đủ 100%."

    def _fetch_dynamic_report_rows(
        self,
        *,
        ten_bao_cao: str,
        ma_bao_cao: str,
        cau_lenh_sql: str,
        tham_so: dict[str, Any],
        max_rows: int,
        timeout: float | None = None,
        progress_callback: Any | None = None,
        page_callback: Any | None = None,
        collect_rows: bool = True,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        fetch_page_size = max(1, int(page_size or self._dynamic_report_fetch_page_size()))
        max_rows = max(1, max_rows)
        rows: list[dict[str, Any]] = []
        columns: list[str] = []
        total = 0
        fetched_rows = 0
        page = 1
        while fetched_rows < max_rows:
            result = self.internal_api.run_sql_report(
                ten_bao_cao=ten_bao_cao,
                ma_bao_cao=ma_bao_cao,
                cau_lenh_sql=cau_lenh_sql,
                tham_so=tham_so,
                page=page,
                page_size=fetch_page_size,
                timeout=timeout,
            )
            if result.get("ok") is False:
                raise RuntimeError(str(result.get("message") or result.get("details") or "API dữ liệu nội bộ trả lỗi."))
            page_rows = result.get("rows") or result.get("data") or []
            if not isinstance(page_rows, list):
                page_rows = []
            if not columns:
                columns = result.get("columns") or self._infer_columns(page_rows)
            if not total:
                try:
                    total = int(result.get("total") or 0)
                except (TypeError, ValueError):
                    total = 0

            remaining = max_rows - fetched_rows
            export_page_rows = page_rows[:remaining]
            if collect_rows:
                rows.extend(export_page_rows)
            if page_callback and export_page_rows:
                page_callback(export_page_rows, columns)
            fetched_rows += len(export_page_rows)
            if progress_callback:
                progress_callback({
                    "page": page,
                    "rows": fetched_rows,
                    "total": total or 0,
                    "page_rows": len(page_rows),
                    "page_size": fetch_page_size,
                    "max_rows": max_rows,
                })

            try:
                result_page_size = int(result.get("page_size") or fetch_page_size)
            except (TypeError, ValueError):
                result_page_size = fetch_page_size
            result_page_size = max(1, result_page_size)

            if not page_rows:
                break
            if total and fetched_rows >= total:
                break
            if len(page_rows) < result_page_size and not total:
                break
            if fetched_rows >= max_rows:
                break
            page += 1

        if not columns:
            columns = self._infer_columns(rows)
        truncated = bool(total and fetched_rows < total) or (not total and fetched_rows >= max_rows)
        return {
            "columns": columns,
            "rows": rows,
            "fetched_rows": fetched_rows,
            "fetched_total": total or fetched_rows,
            "truncated": truncated,
        }

    @classmethod
    def _filter_rows_by_search(cls, rows: list[dict[str, Any]], columns: list[str], search: str) -> list[dict[str, Any]]:
        terms = [term for term in cls._normalize_search_text(search).split(" ") if term]
        if not terms:
            return rows
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for index, row in enumerate(rows):
            haystack = cls._normalize_search_text(" ".join(str(row.get(column, "")) for column in columns))
            if all(term in haystack for term in terms):
                scored.append((cls._search_score(haystack, terms), index, row))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [row for _, _, row in scored]

    @staticmethod
    def _normalize_search_text(value: Any) -> str:
        text = unicodedata.normalize("NFD", str(value or "").casefold())
        text = "".join(character for character in text if unicodedata.category(character) != "Mn")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _search_score(haystack: str, terms: list[str]) -> int:
        score = 0
        full = " ".join(terms)
        if full and full in haystack:
            score += 1000
        for term in terms:
            position = haystack.find(term)
            if position >= 0:
                score += max(1, 200 - position)
        return score

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

    @classmethod
    def _expand_in_list_bind_params(cls, sql: str, filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if not filters:
            return sql, filters

        filters_by_upper = {
            str(key).strip().lstrip(":").upper(): (key, value)
            for key, value in filters.items()
        }
        expanded_filters = dict(filters)

        def replace(match: re.Match[str]) -> str:
            param_name = match.group(1)
            original = filters_by_upper.get(param_name.upper())
            if not original:
                return match.group(0)

            original_key, raw_value = original
            values = cls._bind_list_values(raw_value)
            if not values:
                return match.group(0)
            if len(values) == 1:
                expanded_filters[original_key] = values[0]
                return match.group(0)

            bind_names: list[str] = []
            for index, value in enumerate(values, start=1):
                bind_name = f"{param_name}_{index}"
                expanded_filters[bind_name] = value
                bind_names.append(f":{bind_name}")
            return f"IN ({', '.join(bind_names)})"

        return IN_LIST_BIND_PATTERN.sub(replace, sql), expanded_filters

    @staticmethod
    def _bind_list_values(value: Any) -> list[Any]:
        if isinstance(value, str):
            if "," not in value:
                return []
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple)):
            return [
                item.strip() if isinstance(item, str) else item
                for item in value
                if str(item).strip()
            ]
        return []

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

    @staticmethod
    def _csv_settings(value: Any) -> set[str]:
        return {
            item.strip().upper()
            for item in str(value or "").split(",")
            if item.strip()
        }

    @classmethod
    def dashboard_chart_cache_key(cls, *, report_id: Any, sql_code: str, filters: dict[str, Any], report_code: str | None = None) -> str:
        normalized_filters = json.dumps(filters or {}, ensure_ascii=False, sort_keys=True, default=str)
        identity = str(report_id or report_code or sql_code or "").strip().upper()
        digest = hashlib.sha256(f"{identity}|{normalized_filters}".encode("utf-8")).hexdigest()[:24]
        return f"chart:{digest}"

    def dashboard_chart_cache_enabled_for(self, *, report: dict[str, Any] | None, sql_code: str, report_id: Any = None) -> bool:
        settings = getattr(self.internal_api, "settings", None)
        if not bool(getattr(settings, "dashboard_chart_cache_enabled", True)):
            return False
        if not report:
            return False

        enabled_ids = self._csv_settings(getattr(settings, "dashboard_chart_cache_report_ids", ""))
        enabled_codes = self._csv_settings(getattr(settings, "dashboard_chart_cache_report_codes", ""))
        if "*" in enabled_ids or "*" in enabled_codes or (not enabled_ids and not enabled_codes):
            return True

        candidate_id = str((report or {}).get("id") or report_id or "").strip().upper()
        if candidate_id and candidate_id in enabled_ids:
            return True

        candidates = [
            sql_code,
            (report or {}).get("ma_bao_cao"),
            (report or {}).get("ten_bao_cao"),
        ]
        for candidate in candidates:
            normalized = self._normalized_report_code(candidate)
            raw = str(candidate or "").strip().upper()
            if normalized and normalized in enabled_codes:
                return True
            if raw and raw in enabled_codes:
                return True
        return False

    def dashboard_widget_cache_metadata(
        self,
        *,
        page_id: str,
        tab_id: str,
        row_id: Any,
        widget: dict[str, Any],
        sql_code: str,
        filters: dict[str, Any],
        report: Any = REPORT_NOT_PROVIDED,
    ) -> dict[str, Any] | None:
        if report is REPORT_NOT_PROVIDED:
            report = self._find_sql_report(sql_code, report_id=widget.get("report_id"), report_name=widget.get("title"))
        if not self.dashboard_chart_cache_enabled_for(report=report, sql_code=sql_code, report_id=widget.get("report_id")):
            return None

        report_id = (report or {}).get("id") or widget.get("report_id")
        report_code = (report or {}).get("ma_bao_cao") or sql_code
        return {
            "chart_key": self.dashboard_chart_cache_key(report_id=report_id, sql_code=sql_code, filters=filters, report_code=report_code),
            "page_id": page_id,
            "tab_id": tab_id,
            "widget_key": f"{page_id}:{tab_id}:row:{row_id}:pos:{widget.get('position')}",
            "report_id": report_id,
            "sql_code": sql_code,
            "report_code": report_code,
            "report_name": (report or {}).get("ten_bao_cao") or widget.get("title") or sql_code,
            "widget_title": widget.get("title") or sql_code,
            "widget_type": widget.get("type"),
            "filters": filters or {},
        }

    def _dashboard_cache_result(self, metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        if not metadata or not hasattr(self.app_repository, "get_dashboard_chart_cache"):
            return None
        try:
            entry = self.app_repository.get_dashboard_chart_cache(metadata["chart_key"])
        except RuntimeError as error:
            logger.warning("Cannot read dashboard chart cache %s: %s", metadata.get("chart_key"), error)
            return None
        return self._dashboard_cache_result_from_entry(entry)

    def _dashboard_cache_result_from_entry(self, entry: dict[str, Any] | None) -> dict[str, Any] | None:
        if not entry or entry.get("status") != "success":
            return None
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if not payload:
            return None
        result = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
        details = result.get("details") if isinstance(result.get("details"), dict) else {}
        result["details"] = {
            **details,
            "dashboard_cache": {
                "hit": True,
                "chart_key": entry.get("chart_key"),
                "refreshed_at": entry.get("refreshed_at"),
                "expires_at": entry.get("expires_at"),
            },
        }
        result.setdefault("ok", True)
        result.setdefault("message", "Đã tải dữ liệu biểu đồ từ cache.")
        return result

    def _dashboard_cache_results_by_key(self, metadata_by_query_key: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        if not metadata_by_query_key:
            return {}
        if not hasattr(self.app_repository, "get_dashboard_chart_cache_many"):
            return {
                query_key: result
                for query_key, metadata in metadata_by_query_key.items()
                if (result := self._dashboard_cache_result(metadata))
            }

        chart_keys = [metadata["chart_key"] for metadata in metadata_by_query_key.values()]
        try:
            entries = self.app_repository.get_dashboard_chart_cache_many(chart_keys)
        except RuntimeError as error:
            logger.warning("Cannot read dashboard chart cache in bulk: %s", error)
            return {}

        entry_by_chart_key = {entry.get("chart_key"): entry for entry in entries}
        results: dict[str, dict[str, Any]] = {}
        for query_key, metadata in metadata_by_query_key.items():
            result = self._dashboard_cache_result_from_entry(entry_by_chart_key.get(metadata["chart_key"]))
            if result:
                results[query_key] = result
        return results

    @staticmethod
    def _widget_report_id(widget: dict[str, Any]) -> int | None:
        raw_report_id = widget.get("report_id")
        if raw_report_id in (None, ""):
            return None
        try:
            return int(raw_report_id)
        except (TypeError, ValueError):
            return None

    def _dashboard_reports_by_id(self, tabs: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        report_ids: set[int] = set()
        for tab in tabs:
            for row in tab.get("grid_layout") or []:
                for widget in row.get("widgets") or []:
                    report_id = self._widget_report_id(widget)
                    if report_id is not None:
                        report_ids.add(report_id)
        if not report_ids:
            return {}
        try:
            reports = self.app_repository.list_sql_reports()
        except RuntimeError as error:
            logger.warning("Cannot load SQL report metadata for dashboard cache: %s", error)
            return {}
        reports_by_id: dict[int, dict[str, Any]] = {}
        for report in reports:
            try:
                report_id = int(report.get("id"))
            except (TypeError, ValueError):
                continue
            if report_id in report_ids:
                reports_by_id[report_id] = report
        return reports_by_id

    def save_dashboard_chart_cache(
        self,
        metadata: dict[str, Any] | None,
        result: dict[str, Any],
        *,
        duration_ms: int | None = None,
    ) -> bool:
        if not metadata or not bool(result.get("ok")) or not hasattr(self.app_repository, "upsert_dashboard_chart_cache"):
            return False

        now = datetime.now(UTC)
        ttl_seconds = int(getattr(self.internal_api.settings, "dashboard_chart_cache_ttl_seconds", 300) or 300)
        rows = result.get("rows") if isinstance(result.get("rows"), list) else []
        entry = {
            **metadata,
            "payload": result,
            "status": "success",
            "error_message": None,
            "duration_ms": duration_ms,
            "row_count": len(rows),
            "refreshed_at": now.isoformat(timespec="seconds"),
            "expires_at": (now + timedelta(seconds=max(60, ttl_seconds))).isoformat(timespec="seconds"),
            "updated_at": now.isoformat(timespec="seconds"),
        }
        try:
            self.app_repository.upsert_dashboard_chart_cache(entry)
            return True
        except RuntimeError as error:
            logger.warning("Cannot save dashboard chart cache %s: %s", metadata.get("chart_key"), error)
            return False

    def prune_stale_dashboard_chart_cache(self, active_chart_keys: set[str], page_id: str | None = None) -> int:
        required_methods = ("list_dashboard_chart_cache_keys", "delete_dashboard_chart_cache")
        if not all(hasattr(self.app_repository, name) for name in required_methods):
            return 0
        try:
            existing_keys = set(self.app_repository.list_dashboard_chart_cache_keys(page_id=page_id))
        except RuntimeError as error:
            logger.warning("Cannot list dashboard chart cache keys: %s", error)
            return 0

        deleted = 0
        for chart_key in sorted(existing_keys - active_chart_keys):
            try:
                self.app_repository.delete_dashboard_chart_cache(chart_key)
                deleted += 1
            except RuntimeError as error:
                logger.warning("Cannot delete stale dashboard chart cache %s: %s", chart_key, error)
        return deleted

    def iter_cacheable_dashboard_widgets(
        self,
        page_id_filter: str | None = None,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        widgets: list[tuple[dict[str, Any], dict[str, Any]]] = []
        layouts = self.app_repository.list_dashboard_layouts()
        for layout_summary in layouts:
            page_id = str(layout_summary.get("page_id") or "").strip()
            if page_id_filter and page_id != page_id_filter:
                continue
            layout_row = self.app_repository.get_dashboard_layout(page_id)
            layout = layout_row.get("layout") if layout_row else {}
            tabs = layout.get("tabs") if isinstance(layout.get("tabs"), list) else []
            reports_by_id = self._dashboard_reports_by_id(tabs)
            for tab in tabs:
                tab_id = str(tab.get("tab_id") or "").strip()
                for row in tab.get("grid_layout") or []:
                    row_id = row.get("row_id")
                    for widget in row.get("widgets") or []:
                        sql_code = str(widget.get("sql_code") or "").strip().upper()
                        if not sql_code:
                            continue
                        filters = widget.get("filters") if isinstance(widget.get("filters"), dict) else {}
                        report_id = self._widget_report_id(widget)
                        metadata = self.dashboard_widget_cache_metadata(
                            page_id=page_id,
                            tab_id=tab_id,
                            row_id=row_id,
                            widget=widget,
                            sql_code=sql_code,
                            filters=filters,
                            report=reports_by_id.get(report_id) if report_id is not None else REPORT_NOT_PROVIDED,
                        )
                        if metadata:
                            widgets.append((metadata, widget))
        return widgets

    def refresh_dashboard_chart_cache(self, page_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
        refreshed = 0
        failed = 0
        skipped = 0
        results: list[dict[str, Any]] = []
        seen_chart_keys: set[str] = set()
        cacheable_widgets = self.iter_cacheable_dashboard_widgets(page_id_filter=page_id)
        active_chart_keys = {metadata["chart_key"] for metadata, _ in cacheable_widgets}
        for metadata, widget in cacheable_widgets:
            chart_key = metadata["chart_key"]
            if chart_key in seen_chart_keys:
                skipped += 1
                continue
            seen_chart_keys.add(chart_key)

            started = datetime.now(UTC)
            result = self.run_dynamic_report(
                ma_bao_cao=metadata["sql_code"],
                filters=metadata.get("filters") or {},
                page=1,
                page_size=50,
                report_id=metadata.get("report_id"),
                report_name=metadata.get("report_name") or widget.get("title"),
            )
            duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
            row_count = len(result.get("rows") or []) if isinstance(result.get("rows"), list) else 0
            item = {
                "chart_key": chart_key,
                "report_name": metadata.get("report_name") or metadata["sql_code"],
                "ok": bool(result.get("ok")),
                "message": result.get("message"),
                "row_count": row_count,
                "duration_ms": duration_ms,
            }
            if not result.get("ok"):
                failed += 1
                results.append(item)
                continue
            if not dry_run and self.save_dashboard_chart_cache(metadata, result, duration_ms=duration_ms):
                refreshed += 1
            elif dry_run:
                refreshed += 1
            else:
                failed += 1
                item["ok"] = False
                item["message"] = "Không ghi được cache biểu đồ."
            results.append(item)

        deleted_stale = 0 if dry_run else self.prune_stale_dashboard_chart_cache(active_chart_keys, page_id=page_id)
        return {
            "ok": failed == 0,
            "refreshed": refreshed,
            "failed": failed,
            "skipped": skipped,
            "deleted_stale": deleted_stale,
            "dry_run": dry_run,
            "results": results,
        }

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
        query_jobs: dict[str, dict[str, Any]] = {}
        query_cache_metadata: dict[str, dict[str, Any]] = {}
        reports_by_id = self._dashboard_reports_by_id([tab])
        all_ok = True
        for row in tab.get("grid_layout") or []:
            row_id = row.get("row_id")
            for widget in row.get("widgets") or []:
                sql_code = str(widget.get("sql_code") or "").strip().upper()
                if not sql_code:
                    continue
                filters = widget.get("filters") if isinstance(widget.get("filters"), dict) else {}
                cache_key = self._dashboard_widget_query_key(sql_code, filters, widget.get("report_id"))
                report_id = self._widget_report_id(widget)
                cache_metadata = self.dashboard_widget_cache_metadata(
                    page_id=page_id,
                    tab_id=tab_id,
                    row_id=row_id,
                    widget=widget,
                    sql_code=sql_code,
                    filters=filters,
                    report=reports_by_id.get(report_id) if report_id is not None else REPORT_NOT_PROVIDED,
                )
                query_jobs.setdefault(cache_key, {
                    "ma_bao_cao": sql_code,
                    "filters": filters,
                    "page": 1,
                    "page_size": 50,
                    "report_id": widget.get("report_id"),
                    "report_name": widget.get("title"),
                })
                if cache_metadata:
                    query_cache_metadata.setdefault(cache_key, cache_metadata)
                result = data_cache.get(cache_key) or {}
                all_ok = all_ok and bool(result.get("ok"))
                widget_results.append({
                    "row_id": row_id,
                    "position": widget.get("position"),
                    "type": widget.get("type"),
                    "title": widget.get("title") or sql_code,
                    "sql_code": sql_code,
                    "data": result,
                    "_cache_key": cache_key,
                })

        data_cache.update(self._dashboard_cache_results_by_key(query_cache_metadata))
        for cache_key in data_cache:
            query_jobs.pop(cache_key, None)

        if query_jobs:
            configured_workers = getattr(self.internal_api.settings, "dashboard_tab_max_workers", 10)
            max_workers = min(max(1, int(configured_workers or 10)), 24, len(query_jobs))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_by_key = {
                    executor.submit(self.run_dynamic_report, **job): key
                    for key, job in query_jobs.items()
                }
                for future in as_completed(future_by_key):
                    cache_key = future_by_key[future]
                    result = future.result()
                    data_cache[cache_key] = result
                    self.save_dashboard_chart_cache(query_cache_metadata.get(cache_key), result)

        all_ok = True
        for item in widget_results:
            cache_key = item.pop("_cache_key", "")
            item["data"] = data_cache.get(cache_key, item.get("data") or {})
            all_ok = all_ok and bool((item.get("data") or {}).get("ok"))

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
            return self._failed_report(self._internal_api_connection_message(error), page, page_size, str(error))

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
    def _internal_api_connection_message(error: Exception) -> str:
        detail = str(error).lower()
        if "getaddrinfo" in detail or "name or service not known" in detail or "nodename nor servname" in detail:
            return "Không phân giải được tên miền API dữ liệu nội bộ. Hãy cập nhật URL tunnel/API nội bộ trong Quản trị kết nối."
        if "connection refused" in detail or "actively refused" in detail:
            return "API dữ liệu nội bộ đang từ chối kết nối. Kiểm tra máy chủ API hoặc tunnel đang chạy."
        return "Không kết nối được API dữ liệu nội bộ."

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
            return self._failed_fiber_group(self._internal_api_connection_message(error), str(error))

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
