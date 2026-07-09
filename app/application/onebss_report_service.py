from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any

from app.application.onebss_data_mining_service import (
    EXPORT_DIRECT_SCRIPT,
    LOCAL_TIMEZONE,
    ONEBSS_STATE_PATH,
    REPORT_COMPONENT_READY_SCRIPT,
    OneBssDownloadError,
    OneBssReportDownloader,
    build_target_file_path,
    normalize_onebss_report_url,
    save_downloaded_file,
    with_resolved_schedule_parameters,
)
from app.application.zalo_auto_message_service import install_playwright_chromium, playwright_needs_browser_install
from app.settings import Settings


logger = logging.getLogger(__name__)
OTP_PATTERN = re.compile(r"^\d{6}$")
PENDING_SESSION_TTL_SECONDS = 10 * 60
OTP_TEXT_NEEDLES = ["OTP", "mã OTP", "ma OTP", "mã xác thực", "ma xac thuc", "mã xác nhận", "ma xac nhan"]
OTP_INVALID_TEXT_NEEDLES = ["Số OTP không hợp lệ", "OTP không hợp lệ", "OTP khong hop le"]
OTP_REQUEST_TEXT_NEEDLES = [
    "Gửi yêu cầu",
    "Gui yeu cau",
    "Gửi mã",
    "Gui ma",
    "Gửi OTP",
    "Gui OTP",
    "Xác nhận",
    "Xac nhan",
    "xác nhận đăng nhập",
    "xac nhan dang nhap",
]
OTP_REQUEST_BUTTON_TEXTS = [
    "Gửi yêu cầu",
    "Gui yeu cau",
    "Gửi mã",
    "Gui ma",
    "Gửi OTP",
    "Gui OTP",
    "Xác nhận",
    "Xac nhan",
    "Tiếp tục",
    "Tiep tuc",
    "Đăng nhập",
    "Dang nhap",
]
LOGIN_ERROR_TEXT_NEEDLES = [
    "sai mật khẩu",
    "sai mat khau",
    "không đúng",
    "khong dung",
    "không hợp lệ",
    "khong hop le",
    "tài khoản hoặc mật khẩu",
    "tai khoan hoac mat khau",
]


@dataclass
class PendingOneBssSession:
    session_id: str
    playwright: Any
    browser: Any
    context: Any
    page: Any
    report: dict[str, Any]
    parameters: dict[str, Any]
    created_by: str
    created_at: float


@dataclass
class OneBssParameterRun:
    parameters: dict[str, Any]
    source_values: dict[str, Any]


@dataclass
class OneBssDownloadedFile:
    file_path: Path
    suggested_filename: str
    export_info: dict[str, Any]
    parameters: dict[str, Any]
    source_values: dict[str, Any]


PENDING_ONEBSS_SESSIONS: dict[str, PendingOneBssSession] = {}
PENDING_ONEBSS_LOCK = threading.Lock()


def run_onebss_report_request(
    settings: Settings,
    report: dict[str, Any],
    parameters: dict[str, Any],
    *,
    otp: str = "",
    session_id: str = "",
    created_by: str = "",
) -> dict[str, Any]:
    cleanup_expired_onebss_sessions()
    resolved_parameters = with_resolved_schedule_parameters({"parameters": parameters if isinstance(parameters, dict) else {}})["parameters"]
    if session_id:
        return continue_onebss_report_session(settings, session_id, otp, resolved_parameters)
    return start_onebss_report_session(settings, report, resolved_parameters, created_by=created_by)


def start_onebss_report_session(
    settings: Settings,
    report: dict[str, Any],
    parameters: dict[str, Any],
    *,
    created_by: str = "",
) -> dict[str, Any]:
    report_url = normalize_onebss_report_url(report.get("report_url"))
    username = str(getattr(settings, "onebss_username", "") or "").strip()
    password = settings.onebss_password.get_secret_value() if getattr(settings, "onebss_password", None) else ""
    if not username or not password:
        return {"ok": False, "status": "missing_credentials", "message": "Chua cau hinh ONEBSS_USERNAME/ONEBSS_PASSWORD."}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "status": "missing_playwright", "message": "May chu chua cai Playwright."}

    playwright: Any | None = None
    browser: Any | None = None
    context: Any | None = None
    try:
        playwright = sync_playwright().start()
        try:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        except Exception as launch_error:
            if playwright_needs_browser_install(launch_error):
                install_playwright_chromium()
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            else:
                raise
        context_options: dict[str, Any] = {
            "accept_downloads": True,
            "locale": "vi-VN",
            "viewport": {"width": 1440, "height": 920},
        }
        if ONEBSS_STATE_PATH.exists():
            context_options["storage_state"] = str(ONEBSS_STATE_PATH)
        context = browser.new_context(**context_options)
        page = context.new_page()
        helper = OneBssReportDownloader(settings)
        page.goto(report_url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_load_state("networkidle", timeout=90000)
        page.wait_for_timeout(1000)
        if helper._is_login_page(page):
            helper._fill_first(page, ["input[name='username']", "input[placeholder*='Tài khoản']", "input[placeholder*='Tên']", "input[type='text']"], username)
            helper._fill_first(page, ["input[name='password']", "input[placeholder*='Mật khẩu']", "input[type='password']"], password)
            click_onebss_button(page, helper, ["Đăng nhập", "Dang nhap", "Login"])
            page.wait_for_load_state("networkidle", timeout=90000)
            wait_for_onebss_auth_transition(page, helper)
            if page_contains(page, OTP_TEXT_NEEDLES):
                pending = keep_onebss_session(playwright, browser, context, page, report, parameters, created_by)
                return {
                    "ok": False,
                    "status": "otp_required",
                    "message": "OneBSS yeu cau OTP.",
                    "session_id": pending.session_id,
                    "parameters": parameters,
                }
            device_result = handle_onebss_device_registration(page, helper, parameters)
            if device_result:
                close_browser_stack(browser, context, playwright)
                return device_result
            otp_request_result = handle_onebss_otp_request(page, helper, playwright, browser, context, report, parameters, created_by)
            if otp_request_result:
                return otp_request_result
            if helper._is_login_page(page):
                close_browser_stack(browser, context, playwright)
                return {"ok": False, "status": "login_failed", "message": onebss_login_failed_message(page), "parameters": parameters}
        result = finish_onebss_report_download(settings, helper, context, page, report, parameters)
        close_browser_stack(browser, context, playwright)
        return result
    except Exception as error:
        logger.exception("Cannot start OneBSS report request")
        close_browser_stack(browser, context, playwright)
        return {"ok": False, "status": "failed", "message": str(error)[:1000], "parameters": parameters}


def continue_onebss_report_session(
    settings: Settings,
    session_id: str,
    otp: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    pending = get_onebss_session(session_id)
    if not pending:
        return {"ok": False, "status": "otp_session_expired", "message": "Phien OTP OneBSS da het han, hay bam lay bao cao lai."}
    if not OTP_PATTERN.fullmatch(str(otp or "").strip()):
        return {"ok": False, "status": "otp_required", "message": "OTP phai du 6 chu so.", "session_id": session_id, "parameters": pending.parameters}

    page = pending.page
    context = pending.context
    helper = OneBssReportDownloader(settings)
    try:
        pending.parameters = parameters if parameters else pending.parameters
        helper._fill_otp(page, str(otp).strip())
        click_onebss_button(page, helper, ["Xác nhận", "Xac nhan", "Gửi yêu cầu", "Gui yeu cau", "Đăng nhập", "Dang nhap"])
        page.wait_for_load_state("networkidle", timeout=90000)
        wait_for_onebss_auth_transition(page, helper)
        if page_contains(page, OTP_INVALID_TEXT_NEEDLES):
            return {
                "ok": False,
                "status": "otp_invalid",
                "message": "OTP OneBSS khong hop le, hay nhap lai OTP moi.",
                "session_id": session_id,
                "parameters": pending.parameters,
            }
        if page_contains(page, OTP_TEXT_NEEDLES) and helper._is_login_page(page):
            return {"ok": False, "status": "otp_required", "message": "OneBSS van dang yeu cau OTP.", "session_id": session_id, "parameters": pending.parameters}
        device_result = handle_onebss_device_registration(page, helper, pending.parameters)
        if device_result:
            pop_onebss_session(session_id)
            close_browser_stack(pending.browser, pending.context, pending.playwright)
            return device_result
        if helper._is_login_page(page):
            pop_onebss_session(session_id)
            close_browser_stack(pending.browser, pending.context, pending.playwright)
            return {"ok": False, "status": "login_failed", "message": onebss_login_failed_message(page), "parameters": pending.parameters}
        report_url = normalize_onebss_report_url(pending.report.get("report_url"))
        if page.url != report_url:
            page.goto(report_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_load_state("networkidle", timeout=90000)
        result = finish_onebss_report_download(settings, helper, context, page, pending.report, pending.parameters)
        pop_onebss_session(session_id)
        close_browser_stack(pending.browser, pending.context, pending.playwright)
        return result
    except Exception as error:
        logger.exception("Cannot continue OneBSS report request")
        pop_onebss_session(session_id)
        close_browser_stack(pending.browser, pending.context, pending.playwright)
        return {"ok": False, "status": "failed", "message": str(error)[:1000], "parameters": pending.parameters}


def finish_onebss_report_download(
    settings: Settings,
    helper: OneBssReportDownloader,
    context: Any,
    page: Any,
    report: dict[str, Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    started = time.monotonic()
    report_url = normalize_onebss_report_url(report.get("report_url"))
    schedule_like = {
        "report_url": report_url,
        "storage_link": report.get("storage_link") or "",
        "file_name_template": report.get("ten_bao_cao") or report.get("ma_bao_cao") or "",
    }
    parameter_runs, merge_config, each_keys = build_onebss_parameter_runs(parameters)
    downloaded_files: list[OneBssDownloadedFile] = []
    temporary_files: list[Path] = []
    try:
        if len(parameter_runs) == 1:
            downloaded = download_onebss_report_file(
                settings,
                helper,
                page,
                report,
                parameter_runs[0].parameters,
                source_values=parameter_runs[0].source_values,
            )
            downloaded_files.append(downloaded)
            target_file = downloaded.file_path
            storage_result = save_downloaded_file(settings, target_file, str(report.get("storage_link") or ""))
            context.storage_state(path=str(ONEBSS_STATE_PATH))
            ok = bool(storage_result.get("ok", True))
            export_info = downloaded.export_info
            return {
                "ok": ok,
                "status": "success" if ok else str(storage_result.get("status") or "storage_failed"),
                "message": storage_result.get("message") or "Da tai bao cao OneBSS.",
                "file_name": target_file.name,
                "file_path": str(target_file),
                "storage_link": storage_result.get("storage_link") or str(report.get("storage_link") or ""),
                "storage_status": storage_result.get("storage_status") or "",
                "report_id": export_info.get("report_id") or "",
                "report_title": export_info.get("title") or report.get("ten_bao_cao") or "",
                "parameters": export_info.get("params") or parameter_runs[0].parameters,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "finished_at": datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds"),
            }

        for index, parameter_run in enumerate(parameter_runs, start=1):
            target_file = build_onebss_temp_file_path(settings, index)
            temporary_files.append(target_file)
            downloaded_files.append(
                download_onebss_report_file(
                    settings,
                    helper,
                    page,
                    report,
                    parameter_run.parameters,
                    target_file=target_file,
                    source_values=parameter_run.source_values,
                )
            )

        first_export = downloaded_files[0].export_info if downloaded_files else {}
        target_file = build_target_file_path(
            settings,
            schedule_like,
            suggested_filename=merged_excel_suggested_filename(downloaded_files[0].suggested_filename if downloaded_files else ".xlsx"),
            report_title=str(first_export.get("title") or report.get("ten_bao_cao") or ""),
        )
        merge_onebss_excel_files(downloaded_files, target_file, merge_config, each_keys)
        storage_result = save_downloaded_file(settings, target_file, str(report.get("storage_link") or ""))
        context.storage_state(path=str(ONEBSS_STATE_PATH))
        ok = bool(storage_result.get("ok", True))
        status = "success" if ok else str(storage_result.get("status") or "storage_failed")
        storage_message = storage_result.get("message") or "Da tai bao cao OneBSS."
        merged_message = f"Da tai va gop {len(downloaded_files)} file OneBSS thanh 1 file."
        message = f"{merged_message} {storage_message}" if ok else storage_message
        return {
            "ok": ok,
            "status": status,
            "message": message,
            "file_name": target_file.name,
            "file_path": str(target_file),
            "storage_link": storage_result.get("storage_link") or str(report.get("storage_link") or ""),
            "storage_status": storage_result.get("storage_status") or "",
            "report_id": first_export.get("report_id") or "",
            "report_title": first_export.get("title") or report.get("ten_bao_cao") or "",
            "parameters": parameters,
            "run_parameters": [downloaded.parameters for downloaded in downloaded_files],
            "merged_file_count": len(downloaded_files),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "finished_at": datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds"),
        }
    finally:
        for temporary_file in temporary_files:
            try:
                temporary_file.unlink(missing_ok=True)
            except Exception:
                pass


def download_onebss_report_file(
    settings: Settings,
    helper: OneBssReportDownloader,
    page: Any,
    report: dict[str, Any],
    parameters: dict[str, Any],
    *,
    target_file: Path | None = None,
    source_values: dict[str, Any] | None = None,
) -> OneBssDownloadedFile:
    report_url = normalize_onebss_report_url(report.get("report_url"))
    page.wait_for_function(REPORT_COMPONENT_READY_SCRIPT, timeout=90000)
    export_info: dict[str, Any] = {}
    with page.expect_download(timeout=helper.timeout_ms) as download_info:
        export_info = page.evaluate(EXPORT_DIRECT_SCRIPT, parameters)
    download = download_info.value
    if export_info and not export_info.get("ok", True):
        raise OneBssDownloadError(str(export_info.get("message") or "OneBSS khong tao duoc file xuat."))
    if target_file is None:
        schedule_like = {
            "report_url": report_url,
            "storage_link": report.get("storage_link") or "",
            "file_name_template": report.get("ten_bao_cao") or report.get("ma_bao_cao") or "",
        }
        target_file = build_target_file_path(
            settings,
            schedule_like,
            suggested_filename=download.suggested_filename,
            report_title=str(export_info.get("title") or report.get("ten_bao_cao") or ""),
        )
    target_file.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(str(target_file))
    return OneBssDownloadedFile(
        file_path=target_file,
        suggested_filename=str(download.suggested_filename or target_file.name),
        export_info=export_info,
        parameters=export_info.get("params") if isinstance(export_info.get("params"), dict) else parameters,
        source_values=source_values or {},
    )


def build_onebss_temp_file_path(settings: Settings, index: int) -> Path:
    base_dir = Path(str(getattr(settings, "data_mining_download_dir", "data/data_mining_downloads") or "data/data_mining_downloads"))
    base_dir.mkdir(parents=True, exist_ok=True)
    return (base_dir / f".onebss_part_{uuid.uuid4().hex}_{index}.xlsx").resolve()


def merged_excel_suggested_filename(suggested_filename: str) -> str:
    suffix = Path(str(suggested_filename or "")).suffix.lower()
    if suffix == ".xlsx":
        return suggested_filename
    stem = Path(str(suggested_filename or "onebss_report")).stem or "onebss_report"
    return f"{stem}.xlsx"


def build_onebss_parameter_runs(parameters: dict[str, Any]) -> tuple[list[OneBssParameterRun], dict[str, Any], list[str]]:
    merge_config = parameters.get("$merge_excel") if isinstance(parameters.get("$merge_excel"), dict) else {}
    base_parameters: dict[str, Any] = {}
    each_items: list[tuple[str, list[Any]]] = []
    for key, value in parameters.items():
        if str(key).startswith("$"):
            continue
        if isinstance(value, dict) and "$each" in value:
            each_values = value.get("$each")
            if not isinstance(each_values, list) or not each_values:
                raise OneBssDownloadError(f"Bien {key} dung $each nhung danh sach gia tri dang rong hoac khong hop le.")
            each_items.append((key, each_values))
            continue
        base_parameters[key] = value

    if not each_items:
        return [OneBssParameterRun(parameters=base_parameters, source_values={})], merge_config, []

    runs: list[OneBssParameterRun] = []
    for values in product(*(item[1] for item in each_items)):
        run_parameters = {**base_parameters}
        source_values: dict[str, Any] = {}
        for (key, _), value in zip(each_items, values):
            run_parameters[key] = value
            source_values[key] = value
        runs.append(OneBssParameterRun(parameters=run_parameters, source_values=source_values))
    return runs, merge_config, [item[0] for item in each_items]


def merge_onebss_excel_files(
    downloaded_files: list[OneBssDownloadedFile],
    target_file: Path,
    merge_config: dict[str, Any],
    each_keys: list[str],
) -> None:
    if not downloaded_files:
        raise OneBssDownloadError("Khong co file OneBSS nao de gop.")
    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font
    except ImportError as error:
        raise OneBssDownloadError("May chu chua cai openpyxl de gop file Excel OneBSS.") from error

    output_workbook = Workbook()
    output_sheet = output_workbook.active
    output_sheet.title = safe_excel_sheet_title(str(merge_config.get("sheet") or "DATA"))
    source_column_name = merge_source_column_name(merge_config, each_keys)
    header_signature: tuple[str, ...] | None = None
    header_output_row: int | None = None
    max_columns = 1

    for file_index, downloaded in enumerate(downloaded_files):
        workbook = load_workbook(downloaded.file_path, data_only=False, read_only=True)
        try:
            sheet_name = str(merge_config.get("source_sheet") or "").strip()
            worksheet = workbook[sheet_name] if sheet_name and sheet_name in workbook.sheetnames else workbook.active
            rows = worksheet_rows(worksheet)
        finally:
            workbook.close()
        if not rows:
            continue
        header_index = detect_header_row_index(rows, merge_config)
        if file_index == 0:
            selected_rows = list(enumerate(rows))
            header_signature = row_signature(rows[header_index]) if 0 <= header_index < len(rows) else None
        else:
            start_index = header_index + 1 if header_signature and row_signature(rows[header_index]) == header_signature else int(merge_config.get("skip_rows", 1) or 0)
            selected_rows = list(enumerate(rows[start_index:], start=start_index))

        source_label = merge_source_label(downloaded.source_values, source_column_name)
        for source_row_index, row in selected_rows:
            if file_index > 0 and not row_has_content(row):
                continue
            output_row = trim_trailing_empty_cells(row)
            if source_column_name:
                if source_row_index == header_index:
                    output_row.append(source_column_name)
                elif source_row_index > header_index and row_has_content(row):
                    output_row.append(source_label)
                else:
                    output_row.append("")
            output_sheet.append(output_row)
            max_columns = max(max_columns, len(output_row))
            if file_index == 0 and source_row_index == header_index:
                header_output_row = output_sheet.max_row

    if output_sheet.max_row == 1 and not row_has_content([cell.value for cell in output_sheet[1]]):
        raise OneBssDownloadError("Cac file OneBSS tai ve khong co du lieu de gop.")
    if header_output_row:
        for cell in output_sheet[header_output_row]:
            cell.font = Font(bold=True)
        output_sheet.freeze_panes = f"A{header_output_row + 1}"
    apply_basic_excel_widths(output_sheet, max_columns)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    output_workbook.save(target_file)


def worksheet_rows(worksheet: Any) -> list[list[Any]]:
    rows = [[cell.value for cell in row] for row in worksheet.iter_rows()]
    while rows and not row_has_content(rows[-1]):
        rows.pop()
    return rows


def detect_header_row_index(rows: list[list[Any]], merge_config: dict[str, Any]) -> int:
    configured = merge_config.get("header_row")
    if configured not in {None, ""}:
        try:
            return max(0, min(len(rows) - 1, int(configured) - 1))
        except (TypeError, ValueError):
            pass
    min_cells = int(merge_config.get("min_header_cells") or 2)
    for index, row in enumerate(rows):
        if sum(1 for value in row if value not in {None, ""}) >= min_cells:
            return index
    return 0


def row_has_content(row: list[Any]) -> bool:
    return any(value not in {None, ""} for value in row)


def trim_trailing_empty_cells(row: list[Any]) -> list[Any]:
    trimmed = list(row)
    while trimmed and trimmed[-1] in {None, ""}:
        trimmed.pop()
    return trimmed


def row_signature(row: list[Any]) -> tuple[str, ...]:
    return tuple(str(value or "").strip().lower() for value in trim_trailing_empty_cells(row))


def merge_source_column_name(merge_config: dict[str, Any], each_keys: list[str]) -> str:
    value = merge_config.get("source_column")
    if value is False:
        return ""
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is None and len(each_keys) == 1:
        return each_keys[0]
    if value is True and each_keys:
        return "_".join(each_keys)
    return ""


def merge_source_label(source_values: dict[str, Any], source_column_name: str) -> Any:
    if not source_values or not source_column_name:
        return ""
    if source_column_name in source_values:
        return source_values[source_column_name]
    if len(source_values) == 1:
        return next(iter(source_values.values()))
    return ", ".join(f"{key}={value}" for key, value in source_values.items())


def safe_excel_sheet_title(value: str) -> str:
    title = re.sub(r"[\[\]:*?/\\]", "_", value).strip() or "DATA"
    return title[:31]


def apply_basic_excel_widths(worksheet: Any, max_columns: int) -> None:
    for column_index in range(1, min(max_columns, 80) + 1):
        letter = worksheet.cell(row=1, column=column_index).column_letter
        width = 10
        for row_index in range(1, min(worksheet.max_row, 200) + 1):
            value = worksheet.cell(row=row_index, column=column_index).value
            if value not in {None, ""}:
                width = max(width, min(len(str(value)) + 2, 45))
        worksheet.column_dimensions[letter].width = width


def keep_onebss_session(
    playwright: Any,
    browser: Any,
    context: Any,
    page: Any,
    report: dict[str, Any],
    parameters: dict[str, Any],
    created_by: str,
) -> PendingOneBssSession:
    session = PendingOneBssSession(
        session_id=uuid.uuid4().hex,
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
        report=report,
        parameters=parameters,
        created_by=created_by,
        created_at=time.time(),
    )
    with PENDING_ONEBSS_LOCK:
        PENDING_ONEBSS_SESSIONS[session.session_id] = session
    return session


def get_onebss_session(session_id: str) -> PendingOneBssSession | None:
    with PENDING_ONEBSS_LOCK:
        return PENDING_ONEBSS_SESSIONS.get(session_id)


def pop_onebss_session(session_id: str) -> PendingOneBssSession | None:
    with PENDING_ONEBSS_LOCK:
        return PENDING_ONEBSS_SESSIONS.pop(session_id, None)


def cleanup_expired_onebss_sessions() -> None:
    now = time.time()
    expired: list[PendingOneBssSession] = []
    with PENDING_ONEBSS_LOCK:
        for key, session in list(PENDING_ONEBSS_SESSIONS.items()):
            if now - session.created_at > PENDING_SESSION_TTL_SECONDS:
                expired.append(PENDING_ONEBSS_SESSIONS.pop(key))
    for session in expired:
        close_browser_stack(session.browser, session.context, session.playwright)


def close_browser_stack(browser: Any, context: Any, playwright: Any | None = None) -> None:
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
    if playwright is not None:
        try:
            playwright.stop()
        except Exception:
            pass


def wait_for_onebss_auth_transition(page: Any, helper: OneBssReportDownloader, timeout_ms: int = 12000) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    device_needles = ["ĐĂNG KÝ THIẾT BỊ", "DANG KY THIET BI", "đăng ký thiết bị", "dang ky thiet bi"]
    while time.monotonic() < deadline:
        if (
            page_contains(page, OTP_TEXT_NEEDLES)
            or page_contains(page, OTP_INVALID_TEXT_NEEDLES)
            or page_contains(page, LOGIN_ERROR_TEXT_NEEDLES)
            or page_contains(page, device_needles)
            or page_contains(page, OTP_REQUEST_TEXT_NEEDLES)
        ):
            return
        try:
            if not helper._is_login_page(page):
                return
        except Exception:
            return
        try:
            page.wait_for_timeout(500)
        except Exception:
            time.sleep(0.5)


def click_onebss_button(page: Any, helper: OneBssReportDownloader, texts: list[str]) -> bool:
    if helper._click_button_text(page, texts):
        return True
    try:
        clicked = page.evaluate(
            """
            (texts) => {
              const normalize = (value) => String(value || '')
                .normalize('NFD')
                .replace(/[\\u0300-\\u036f]/g, '')
                .replace(/\\s+/g, ' ')
                .trim()
                .toLowerCase();
              const wanted = texts.map(normalize).filter(Boolean);
              const buttons = Array.from(document.querySelectorAll('button'));
              const visible = buttons.filter((button) => {
                const rect = button.getBoundingClientRect();
                const style = window.getComputedStyle(button);
                return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none' && !button.disabled;
              });
              const matched = visible.find((button) => {
                const text = normalize(button.innerText || button.textContent || button.value);
                return wanted.some((item) => text === item || text.includes(item));
              });
              const target = matched || (visible.length === 1 ? visible[0] : null);
              if (!target) return false;
              target.click();
              return true;
            }
            """,
            texts,
        )
        if clicked:
            return True
    except Exception:
        pass
    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False


def handle_onebss_otp_request(
    page: Any,
    helper: OneBssReportDownloader,
    playwright: Any,
    browser: Any,
    context: Any,
    report: dict[str, Any],
    parameters: dict[str, Any],
    created_by: str,
) -> dict[str, Any] | None:
    if page_contains(page, LOGIN_ERROR_TEXT_NEEDLES):
        return None
    url = str(getattr(page, "url", "") or "").lower()
    url_indicates_otp_flow = "auth/login" in url and ("username=" in url or "deviceid=" in url)
    if not url_indicates_otp_flow and not page_contains(page, OTP_REQUEST_TEXT_NEEDLES):
        return None

    clicked_any = False
    for _ in range(3):
        if page_contains(page, OTP_TEXT_NEEDLES):
            break
        clicked = click_onebss_button(page, helper, OTP_REQUEST_BUTTON_TEXTS)
        if not clicked:
            break
        clicked_any = True
        page.wait_for_load_state("networkidle", timeout=90000)
        page.wait_for_timeout(1000)

    if not clicked_any and not page_contains(page, OTP_TEXT_NEEDLES) and not url_indicates_otp_flow:
        return None

    pending = keep_onebss_session(playwright, browser, context, page, report, parameters, created_by)
    return {
        "ok": False,
        "status": "otp_required",
        "message": "OneBSS da gui yeu cau OTP. Hay nhap ma OTP khi dien thoai nhan duoc.",
        "session_id": pending.session_id,
        "parameters": parameters,
    }


def handle_onebss_device_registration(page: Any, helper: OneBssReportDownloader, parameters: dict[str, Any]) -> dict[str, Any] | None:
    if not page_contains(page, ["ĐĂNG KÝ THIẾT BỊ", "DANG KY THIET BI", "đăng ký thiết bị", "dang ky thiet bi"]):
        return None
    try:
        checkbox = page.locator("input[type='checkbox']").first
        if checkbox.count():
            checkbox.check(force=True, timeout=10000)
        clicked = helper._click_button_text(
            page,
            ["Gửi yêu cầu đăng ký", "Gui yeu cau dang ky", "Gửi yêu cầu", "Gui yeu cau", "Xác nhận", "Xac nhan"],
        )
        if not clicked:
            return {
                "ok": False,
                "status": "device_registration_required",
                "message": "OneBSS yeu cau dang ky thiet bi moi nhung khong tim thay nut gui yeu cau.",
                "parameters": parameters,
            }
        page.wait_for_load_state("networkidle", timeout=90000)
        page.wait_for_timeout(1000)
    except Exception as error:
        logger.exception("Cannot send OneBSS device registration request")
        return {
            "ok": False,
            "status": "device_registration_failed",
            "message": f"Khong gui duoc yeu cau dang ky thiet bi OneBSS: {error}",
            "parameters": parameters,
        }
    if page_contains(page, ["ĐĂNG KÝ THIẾT BỊ", "DANG KY THIET BI", "chờ phê duyệt", "cho phe duyet"]):
        return {
            "ok": False,
            "status": "device_registration_pending",
            "message": "Da gui yeu cau dang ky thiet bi OneBSS va dang cho phe duyet.",
            "parameters": parameters,
        }
    return None


def onebss_login_failed_message(page: Any) -> str:
    url = str(getattr(page, "url", "") or "")
    try:
        text = " ".join(str(page.locator("body").inner_text(timeout=3000) or "").split())
    except Exception:
        text = ""
    if text:
        return f"Dang nhap OneBSS chua thanh cong. Trang hien tai: {url}. Noi dung: {text[:300]}"
    return f"Dang nhap OneBSS chua thanh cong. Trang hien tai: {url}"


def page_contains(page: Any, needles: list[str]) -> bool:
    try:
        text = page.locator("body").inner_text(timeout=5000).lower()
    except Exception:
        return False
    return any(needle.lower() in text for needle in needles)
