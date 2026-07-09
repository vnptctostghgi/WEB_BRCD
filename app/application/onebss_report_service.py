from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
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
            helper._fill_first(page, ["input[name='username']", "input[placeholder*='Tên']", "input[type='text']"], username)
            helper._fill_first(page, ["input[name='password']", "input[type='password']"], password)
            helper._click_button_text(page, ["Đăng nhập", "Dang nhap", "Login"])
            page.wait_for_load_state("networkidle", timeout=90000)
            page.wait_for_timeout(1500)
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
        helper._click_button_text(page, ["Xác nhận", "Xac nhan", "Gửi yêu cầu", "Gui yeu cau", "Đăng nhập", "Dang nhap"])
        page.wait_for_load_state("networkidle", timeout=90000)
        page.wait_for_timeout(1500)
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
    page.wait_for_function(REPORT_COMPONENT_READY_SCRIPT, timeout=90000)
    export_info: dict[str, Any] = {}
    with page.expect_download(timeout=helper.timeout_ms) as download_info:
        export_info = page.evaluate(EXPORT_DIRECT_SCRIPT, parameters)
    download = download_info.value
    if export_info and not export_info.get("ok", True):
        raise OneBssDownloadError(str(export_info.get("message") or "OneBSS khong tao duoc file xuat."))
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
    storage_result = save_downloaded_file(settings, target_file, str(report.get("storage_link") or ""))
    context.storage_state(path=str(ONEBSS_STATE_PATH))
    ok = bool(storage_result.get("ok", True))
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
        "parameters": export_info.get("params") or parameters,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "finished_at": datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds"),
    }


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
        clicked = helper._click_button_text(page, OTP_REQUEST_BUTTON_TEXTS)
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
