from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
import sys
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse

from itsdangerous import TimestampSigner

from app.application.database_service import DatabaseService
from app.application.zalo_bot import ZaloBotClient
from app.data_access.app_repository import DEFAULT_DASHBOARD_PAGE_ID, dashboard_feature_code_for_page, normalize_feature_code
from app.data_access.internal_api_client import InternalApiClient
from app.settings import Settings


logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "brcd_session"
DASHBOARD_CAPTURE_SELECTOR = "#dashboard-viewer-capture-area"
DASHBOARD_SECTION_SELECTOR = "#dashboard-designed-section"
PUBLIC_USER_KEYS = (
    "id",
    "username",
    "full_name",
    "employee_code",
    "email",
    "phone",
    "birth_date",
    "gender",
    "department",
    "job_title",
    "role",
    "is_active",
    "must_change_password",
)


def public_base_url(settings: Settings) -> str:
    configured = str(getattr(settings, "app_public_url", "") or "").strip().rstrip("/")
    if configured:
        return configured
    webhook_url = str(getattr(settings, "zalo_webhook_url", "") or "").strip()
    if "/api/zalo/webhook" in webhook_url:
        return webhook_url.split("/api/zalo/webhook", 1)[0].rstrip("/")
    parsed = urlparse(webhook_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return ""


def capture_public_url(settings: Settings, capture: dict[str, Any] | None) -> str:
    if not capture:
        return ""
    base_url = public_base_url(settings)
    capture_id = str(capture.get("capture_id") or "").strip()
    token = str(capture.get("public_token") or "").strip()
    if not base_url or not capture_id or not token:
        return ""
    return f"{base_url}/api/zalo/auto-message-captures/{quote(capture_id)}?token={quote(token)}"


def latest_zalo_chat_id_from_logs(repository: Any) -> str:
    for row in repository.list_audit_logs(limit=500):
        if row.get("action") != "zalo_message_received":
            continue
        try:
            details = json.loads(row.get("details") or "{}")
        except json.JSONDecodeError:
            continue
        chat_id = str(details.get("chat_id") or "").strip()
        if chat_id:
            return chat_id
    return ""


def auto_message_caption(schedule: dict[str, Any]) -> str:
    caption = str(schedule.get("caption") or "").strip()
    if caption:
        return caption
    title = str(schedule.get("name") or "Anh chup tu dong").strip()
    page = str(schedule.get("page_label") or schedule.get("page_url") or "").strip()
    return f"{title}\n{page}" if page else title


def log_zalo_auto_message(repository: Any, schedule: dict[str, Any], chat_id: str, text: str, ok: bool, photo_url: str) -> None:
    details = {
        "direction": "out",
        "event_name": "auto_schedule",
        "chat_id": chat_id,
        "chat_type": schedule.get("target_type") or "",
        "sender_id": "",
        "sender_name": schedule.get("chat_name") or "",
        "message_id": "",
        "text": text[:1000],
        "ok": ok,
        "raw_preview": photo_url[:1800],
        "raw_keys": [],
        "result_keys": [],
        "message_keys": [],
    }
    repository.add_audit_log(
        "zalo_auto",
        "zalo_message_sent" if ok else "zalo_message_send_failed",
        json.dumps(details, ensure_ascii=False),
    )
    repository.add_audit_log(
        "zalo_auto",
        "zalo_auto_message_sent" if ok else "zalo_auto_message_failed",
        f"{schedule.get('schedule_id')}: {schedule.get('name')} -> {chat_id}",
    )


def resolve_zalo_auto_photo_url(repository: Any, settings: Settings, schedule: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    latest_capture = repository.get_latest_zalo_message_capture(str(schedule.get("schedule_id") or ""), include_image=False)
    capture_url = capture_public_url(settings, latest_capture)
    if capture_url:
        return capture_url, latest_capture
    photo_url = str(schedule.get("photo_url") or "").strip()
    return photo_url, latest_capture


def schedule_page_url(settings: Settings, schedule: dict[str, Any]) -> tuple[str, str]:
    base_url = public_base_url(settings)
    if not base_url:
        return "", ""
    raw_page_url = str(schedule.get("page_url") or "/").strip() or "/"
    parsed_base = urlparse(base_url)
    parsed_page = urlparse(raw_page_url)
    if parsed_page.scheme and parsed_page.netloc:
        if parsed_page.scheme != parsed_base.scheme or parsed_page.netloc != parsed_base.netloc:
            return "", ""
        path = parsed_page.path or "/"
        if parsed_page.query:
            path = f"{path}?{parsed_page.query}"
        return raw_page_url, path
    if not raw_page_url.startswith("/"):
        raw_page_url = f"/{raw_page_url}"
    return urljoin(f"{base_url}/", raw_page_url.lstrip("/")), raw_page_url


def schedule_feature_code(schedule: dict[str, Any]) -> str:
    raw_page_url = str(schedule.get("page_url") or "/").strip() or "/"
    parsed = urlparse(raw_page_url)
    path = unquote(parsed.path or raw_page_url).strip("/")
    if not path or path.lower() == "dashboard":
        return "dashboard"
    first_segment = path.split("/", 1)[0]
    return normalize_feature_code(first_segment) or "dashboard"


def dashboard_page_id_for_schedule(repository: Any, schedule: dict[str, Any]) -> str:
    feature_code = schedule_feature_code(schedule)
    if feature_code == "dashboard":
        return DEFAULT_DASHBOARD_PAGE_ID
    normalized_feature = normalize_feature_code(feature_code)
    try:
        layouts = repository.list_dashboard_layouts()
    except Exception as error:
        logger.warning("Cannot list dashboard layouts before Zalo capture: %s", error)
        layouts = []
    for layout in layouts:
        page_id = str(layout.get("page_id") or "").strip()
        if not page_id:
            continue
        layout_feature_code = dashboard_feature_code_for_page(page_id)
        if layout_feature_code == feature_code or normalize_feature_code(layout_feature_code) == normalized_feature:
            return page_id
    fallback = re.sub(r"[^A-Za-z0-9]+", "", feature_code).upper()
    return fallback or DEFAULT_DASHBOARD_PAGE_ID


def refresh_schedule_data(repository: Any, settings: Settings, schedule: dict[str, Any]) -> dict[str, Any]:
    page_id = dashboard_page_id_for_schedule(repository, schedule)
    result = DatabaseService(InternalApiClient(settings), repository).refresh_dashboard_chart_cache(page_id=page_id)
    result["page_id"] = page_id
    return result


def public_user_for_capture(user: dict[str, Any]) -> dict[str, Any]:
    return {key: user.get(key) for key in PUBLIC_USER_KEYS if key in user}


def capture_admin_user(repository: Any, settings: Settings) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    try:
        candidates = repository.list_users()
    except Exception as error:
        logger.warning("Cannot list users for Zalo auto capture: %s", error)
    for user in candidates:
        if user.get("role") == "admin" and user.get("is_active") and not user.get("must_change_password"):
            return user
    admin_username = str(getattr(settings, "initial_admin_username", "") or "").strip()
    if admin_username:
        try:
            user = repository.get_user_by_username(admin_username)
            if user and user.get("role") == "admin" and user.get("is_active"):
                return user
        except Exception as error:
            logger.warning("Cannot load initial admin for Zalo auto capture: %s", error)
    for user in candidates:
        if user.get("role") == "admin" and user.get("is_active"):
            return user
    return None


def signed_capture_session_cookie(settings: Settings, user: dict[str, Any]) -> str:
    payload = {"user": public_user_for_capture(user)}
    data = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    signer = TimestampSigner(settings.session_secret.get_secret_value())
    return signer.sign(data).decode("utf-8")


def playwright_session_cookie(settings: Settings, user: dict[str, Any]) -> dict[str, Any]:
    base_url = public_base_url(settings)
    parsed_base = urlparse(base_url)
    return {
        "name": SESSION_COOKIE_NAME,
        "value": signed_capture_session_cookie(settings, user),
        "url": base_url,
        "httpOnly": True,
        "secure": parsed_base.scheme == "https",
        "sameSite": "Lax",
    }


def playwright_needs_browser_install(error: Exception) -> bool:
    message = str(error).lower()
    return "executable doesn't exist" in message or "please run the following command" in message or "playwright install" in message


def install_playwright_chromium() -> None:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def capture_schedule_page_image(repository: Any, settings: Settings, schedule: dict[str, Any]) -> dict[str, Any]:
    target_url, path = schedule_page_url(settings, schedule)
    if not target_url:
        return {"ok": False, "message": "Chua cau hinh APP_PUBLIC_URL/ZALO_WEBHOOK_URL hop le de tu chup anh."}
    try:
        screenshot_bytes = capture_page_screenshot_bytes(
            repository,
            settings,
            str(schedule.get("page_url") or "/"),
            selector=DASHBOARD_CAPTURE_SELECTOR,
        )
    except Exception as error:
        logger.exception("Cannot capture Zalo auto message page %s", target_url)
        return {"ok": False, "message": "Khong chup duoc anh moi cua trang chuc nang.", "error": str(error)[:500]}

    image_base64 = base64.b64encode(screenshot_bytes).decode("ascii")
    capture = repository.save_zalo_message_capture(
        str(schedule.get("schedule_id") or ""),
        image_base64,
        "image/png",
        path or "/",
        "zalo_auto",
    )
    capture_url = capture_public_url(settings, capture)
    if not capture_url:
        return {"ok": False, "message": "Da chup anh nhung khong tao duoc URL cong khai de gui Zalo.", "capture": capture}
    return {"ok": True, "message": "Da chup anh moi.", "capture": capture, "capture_url": capture_url, "page_url": target_url}


def capture_failure_message(capture_result: dict[str, Any]) -> str:
    message = str(capture_result.get("message") or "Chua chup duoc anh moi cho lich gui Zalo.").strip()
    error = str(capture_result.get("error") or "").strip()
    if error:
        return f"{message} Chi tiet: {error[:240]}"
    return message


def capture_page_screenshot_bytes(repository: Any, settings: Settings, page_url: str, selector: str = DASHBOARD_CAPTURE_SELECTOR) -> bytes:
    schedule = {"page_url": page_url or "/"}
    target_url, _path = schedule_page_url(settings, schedule)
    if not target_url:
        raise RuntimeError("Chua cau hinh APP_PUBLIC_URL/ZALO_WEBHOOK_URL hop le de chup anh.")
    admin_user = capture_admin_user(repository, settings)
    if not admin_user:
        raise RuntimeError("Chua co tai khoan admin hoat dong de chup anh.")
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("May chu chua cai Playwright de chup anh.") from error

    session_cookie = playwright_session_cookie(settings, admin_user)

    def run_capture(install_retry: bool = False) -> bytes:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                try:
                    context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=2, locale="vi-VN")
                    context.add_cookies([session_cookie])
                    page = context.new_page()
                    page.goto(target_url, wait_until="networkidle", timeout=90000)
                    try:
                        page.wait_for_selector(DASHBOARD_SECTION_SELECTOR, state="visible", timeout=30000)
                        page.wait_for_function(
                            """
                            () => {
                              const loadedAt = document.querySelector('#dashboard-viewer-loaded-at')?.textContent || '';
                              const tabs = document.querySelector('#dashboard-viewer-tabs');
                              const workspace = document.querySelector('#dashboard-viewer-workspace');
                              const bodyBusy = document.body.classList.contains('view-loading');
                              const text = workspace?.innerText || '';
                              return !bodyBusy
                                && tabs && tabs.children.length > 0
                                && workspace && workspace.children.length > 0
                                && loadedAt && !loadedAt.includes('Chưa tải')
                                && !text.includes('Chưa tải dữ liệu')
                                && !text.includes('Đang tải');
                            }
                            """,
                            timeout=90000,
                        )
                        page.wait_for_selector(selector, state="visible", timeout=30000)
                        page.wait_for_function(
                            "() => document.querySelectorAll('[data-dashboard-sheet-state=\"loading\"]').length === 0",
                            timeout=30000,
                        )
                    except PlaywrightTimeoutError:
                        raise RuntimeError("Dashboard chua tai xong du lieu de chup anh.") from None
                    page.wait_for_timeout(1800)
                    locator = page.locator(selector).first
                    if locator.count():
                        return locator.screenshot(type="png")
                    raise RuntimeError("Khong tim thay vung Dashboard de chup anh.")
                finally:
                    browser.close()
        except Exception as error:
            if not install_retry and playwright_needs_browser_install(error):
                install_playwright_chromium()
                return run_capture(install_retry=True)
            raise

    return run_capture()


def send_zalo_auto_message(repository: Any, settings: Settings, schedule: dict[str, Any]) -> dict[str, Any]:
    chat_id = str(schedule.get("chat_id") or "").strip() or latest_zalo_chat_id_from_logs(repository)
    if not chat_id:
        return {"ok": False, "message": "Chua co chat_id Zalo de gui lich tu dong.", "chat_id": "", "photo_url": ""}
    try:
        refresh_result = refresh_schedule_data(repository, settings, schedule)
    except Exception as error:
        logger.exception("Cannot refresh data before Zalo auto message")
        return {
            "ok": False,
            "message": "Khong load duoc du lieu moi nhat truoc khi gui Zalo.",
            "chat_id": chat_id,
            "photo_url": "",
            "error": str(error)[:500],
        }
    if not refresh_result.get("ok"):
        return {
            "ok": False,
            "message": "Du lieu moi nhat chua san sang, chua gui anh Zalo.",
            "chat_id": chat_id,
            "photo_url": "",
            "refresh_result": refresh_result,
        }

    capture_result = capture_schedule_page_image(repository, settings, schedule)
    latest_capture = capture_result.get("capture") if capture_result.get("ok") else None
    photo_url = str(capture_result.get("capture_url") or "").strip()
    if not photo_url:
        return {
            "ok": False,
            "message": capture_failure_message(capture_result),
            "chat_id": chat_id,
            "photo_url": "",
            "latest_capture": latest_capture,
            "capture_result": capture_result,
        }
    parsed = urlparse(photo_url)
    if parsed.scheme != "https":
        return {"ok": False, "message": "URL anh gui Zalo phai dung HTTPS.", "chat_id": chat_id, "photo_url": photo_url}
    caption = auto_message_caption(schedule)
    sent = ZaloBotClient(settings).send_photo(chat_id, photo_url, caption)
    log_zalo_auto_message(repository, schedule, chat_id, caption, sent, photo_url)
    if not sent:
        return {"ok": False, "message": "Khong gui duoc anh qua Zalo.", "chat_id": chat_id, "photo_url": photo_url}
    return {"ok": True, "message": "Da gui anh qua Zalo.", "chat_id": chat_id, "photo_url": photo_url, "caption": caption}
