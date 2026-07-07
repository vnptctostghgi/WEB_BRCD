from __future__ import annotations

import logging
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.google_drive_service import (
    GoogleDriveConfigurationError,
    extract_google_drive_folder_id,
    google_drive_folder_id,
    upload_file_to_google_drive,
)
from app.application.zalo_auto_message_service import install_playwright_chromium, playwright_needs_browser_install
from app.settings import Settings


logger = logging.getLogger(__name__)
try:
    LOCAL_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
except ZoneInfoNotFoundError:
    LOCAL_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


ONEBSS_HOST = "onebss.vnpt.vn"
ONEBSS_STATE_PATH = Path("data/onebss_browser_state.json")
FILENAME_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


class OneBssDownloadError(RuntimeError):
    """Raised when OneBSS automation cannot finish a report download."""


def run_data_mining_schedule(
    repository: Any,
    settings: Settings,
    schedule: dict[str, Any],
    *,
    otp: str = "",
    created_by: str = "",
    allow_device_registration: bool = False,
    interactive: bool = False,
) -> dict[str, Any]:
    run = repository.create_data_mining_run(
        str(schedule.get("schedule_id") or ""),
        schedule.get("parameters") if isinstance(schedule.get("parameters"), dict) else {},
        created_by=created_by,
    )
    started = time.monotonic()
    try:
        result = OneBssReportDownloader(settings).download_report(
            schedule,
            otp=otp,
            allow_device_registration=allow_device_registration,
            interactive=interactive,
        )
    except Exception as error:
        logger.exception("OneBSS data mining failed for %s", schedule.get("schedule_id"))
        result = {
            "ok": False,
            "status": "failed",
            "message": str(error)[:1000] or "Khong tai duoc bao cao OneBSS.",
        }
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    repository.finish_data_mining_run(str(run.get("run_id") or ""), result)
    return {**result, "run_id": run.get("run_id"), "schedule_id": schedule.get("schedule_id")}


class OneBssReportDownloader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout_ms = max(30, int(getattr(settings, "onebss_download_timeout_seconds", 180) or 180)) * 1000

    def download_report(
        self,
        schedule: dict[str, Any],
        *,
        otp: str = "",
        allow_device_registration: bool = False,
        interactive: bool = False,
    ) -> dict[str, Any]:
        report_url = normalize_onebss_report_url(schedule.get("report_url"))
        parameters = schedule.get("parameters") if isinstance(schedule.get("parameters"), dict) else {}
        username = str(getattr(self.settings, "onebss_username", "") or "").strip()
        password = self.settings.onebss_password.get_secret_value() if getattr(self.settings, "onebss_password", None) else ""
        if not username or not password:
            return {
                "ok": False,
                "status": "missing_credentials",
                "message": "Chua cau hinh ONEBSS_USERNAME/ONEBSS_PASSWORD tren bien moi truong.",
            }

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise OneBssDownloadError("May chu chua cai Playwright de tu dong tai bao cao OneBSS.") from error

        def run_browser(install_retry: bool = False) -> dict[str, Any]:
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                    try:
                        context_options: dict[str, Any] = {
                            "accept_downloads": True,
                            "locale": "vi-VN",
                            "viewport": {"width": 1440, "height": 920},
                        }
                        if ONEBSS_STATE_PATH.exists():
                            context_options["storage_state"] = str(ONEBSS_STATE_PATH)
                        context = browser.new_context(**context_options)
                        page = context.new_page()
                        page.goto(report_url, wait_until="domcontentloaded", timeout=90000)
                        page.wait_for_load_state("networkidle", timeout=90000)
                        if self._is_login_page(page):
                            if not interactive and not otp:
                                return {
                                    "ok": False,
                                    "status": "otp_required",
                                    "message": "Chua co phien OneBSS hop le. Can chay thu voi OTP truoc khi bat lich tu dong.",
                                }
                            login_result = self._login(page, username, password, otp, allow_device_registration)
                            if not login_result.get("ok"):
                                return login_result
                            ONEBSS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                            context.storage_state(path=str(ONEBSS_STATE_PATH))
                            page.goto(report_url, wait_until="domcontentloaded", timeout=90000)
                            page.wait_for_load_state("networkidle", timeout=90000)

                        try:
                            self._wait_for_report_component(page)
                        except PlaywrightTimeoutError as error:
                            if self._is_login_page(page):
                                return {
                                    "ok": False,
                                    "status": "otp_required",
                                    "message": "Phien OneBSS da het han hoac chua xac thuc OTP.",
                                }
                            raise OneBssDownloadError("Trang bao cao OneBSS chua tai xong nut xuat du lieu.") from error

                        export_info: dict[str, Any] = {}
                        try:
                            with page.expect_download(timeout=self.timeout_ms) as download_info:
                                export_info = page.evaluate(EXPORT_DIRECT_SCRIPT, parameters)
                            download = download_info.value
                        except PlaywrightTimeoutError as error:
                            export_message = str(export_info.get("message") or "").strip()
                            raise OneBssDownloadError(export_message or "OneBSS chua tra file tai xuong trong thoi gian cho.") from error
                        if export_info and not export_info.get("ok", True):
                            raise OneBssDownloadError(str(export_info.get("message") or "OneBSS khong tao duoc file xuat."))

                        target_file = build_target_file_path(
                            self.settings,
                            schedule,
                            suggested_filename=download.suggested_filename,
                            report_title=str(export_info.get("title") or ""),
                        )
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        download.save_as(str(target_file))
                        storage_result = save_downloaded_file(self.settings, target_file, str(schedule.get("storage_link") or ""))
                        ok = bool(storage_result.get("ok", True))
                        context.storage_state(path=str(ONEBSS_STATE_PATH))
                        return {
                            "ok": ok,
                            "status": "success" if ok else str(storage_result.get("status") or "storage_failed"),
                            "message": storage_result.get("message") or "Da tai bao cao OneBSS.",
                            "file_name": target_file.name,
                            "file_path": str(target_file),
                            "storage_link": storage_result.get("storage_link") or str(schedule.get("storage_link") or ""),
                            "storage_status": storage_result.get("storage_status") or "",
                            "report_id": export_info.get("report_id") or "",
                            "report_title": export_info.get("title") or "",
                            "parameters": export_info.get("params") or parameters,
                        }
                    finally:
                        browser.close()
            except Exception as error:
                if not install_retry and playwright_needs_browser_install(error):
                    install_playwright_chromium()
                    return run_browser(install_retry=True)
                raise

        return run_browser()

    def _login(
        self,
        page: Any,
        username: str,
        password: str,
        otp: str,
        allow_device_registration: bool,
    ) -> dict[str, Any]:
        self._fill_first(page, ["input[name='username']", "input[placeholder*='Tên']", "input[type='text']"], username)
        self._fill_first(page, ["input[name='password']", "input[type='password']"], password)
        self._click_button_text(page, ["Đăng nhập", "Dang nhap", "Login"])
        page.wait_for_load_state("networkidle", timeout=90000)

        if self._page_contains(page, ["mã OTP", "ma OTP", "OTP"]):
            if not otp:
                return {
                    "ok": False,
                    "status": "otp_required",
                    "message": "OneBSS da yeu cau OTP. Hay nhap OTP va chay thu lai.",
                }
            self._fill_otp(page, otp)
            self._click_button_text(page, ["Xác nhận", "Xac nhan", "Gửi yêu cầu", "Gui yeu cau", "Đăng nhập", "Dang nhap"])
            page.wait_for_load_state("networkidle", timeout=90000)

        if self._page_contains(page, ["ĐĂNG KÝ THIẾT BỊ", "DANG KY THIET BI", "đăng ký thiết bị", "dang ky thiet bi"]):
            if not allow_device_registration:
                return {
                    "ok": False,
                    "status": "device_registration_required",
                    "message": "OneBSS yeu cau dang ky thiet bi moi. Hay cho phep dang ky khi chay thu.",
                }
            checkbox = page.locator("input[type='checkbox']").first
            if checkbox.count():
                checkbox.check(force=True, timeout=10000)
            self._click_button_text(page, ["Gửi yêu cầu đăng ký", "Gui yeu cau dang ky", "Gửi yêu cầu", "Gui yeu cau"])
            page.wait_for_load_state("networkidle", timeout=90000)
            if self._page_contains(page, ["chờ phê duyệt", "cho phe duyet"]):
                return {
                    "ok": False,
                    "status": "device_registration_pending",
                    "message": "Da gui yeu cau dang ky thiet bi OneBSS va dang cho phe duyet.",
                }
        if self._is_login_page(page):
            return {"ok": False, "status": "login_failed", "message": "Dang nhap OneBSS chua thanh cong."}
        return {"ok": True}

    def _wait_for_report_component(self, page: Any) -> None:
        page.wait_for_function(REPORT_COMPONENT_READY_SCRIPT, timeout=90000)

    def _is_login_page(self, page: Any) -> bool:
        try:
            url = page.url or ""
            return "/auth/login" in url or self._page_contains(page, ["Đăng nhập", "Dang nhap", "Tên đăng nhập", "Ten dang nhap"])
        except Exception:
            return False

    @staticmethod
    def _page_contains(page: Any, needles: list[str]) -> bool:
        try:
            text = page.locator("body").inner_text(timeout=5000)
        except Exception:
            return False
        text_lower = text.lower()
        return any(needle.lower() in text_lower for needle in needles)

    @staticmethod
    def _fill_first(page: Any, selectors: list[str], value: str) -> bool:
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count():
                locator.first.fill(value, timeout=10000)
                return True
        return False

    @staticmethod
    def _fill_otp(page: Any, otp: str) -> bool:
        selectors = [
            "input[name*='otp' i]",
            "input[placeholder*='OTP']",
            "input[type='tel']",
            "input[type='number']",
        ]
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count():
                locator.first.fill(otp, timeout=10000)
                return True
        inputs = page.locator("input")
        count = inputs.count()
        if count:
            inputs.nth(count - 1).fill(otp, timeout=10000)
            return True
        return False

    @staticmethod
    def _click_button_text(page: Any, texts: list[str]) -> bool:
        for text in texts:
            locator = page.locator("button").filter(has_text=text)
            if locator.count():
                locator.first.click(timeout=15000)
                return True
        button = page.locator("button[type='submit']")
        if button.count():
            button.first.click(timeout=15000)
            return True
        return False


def normalize_onebss_report_url(raw_url: Any) -> str:
    url = str(raw_url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OneBssDownloadError("Link bao cao OneBSS chua hop le.")
    if ONEBSS_HOST not in parsed.netloc.lower():
        raise OneBssDownloadError("Chi cho phep tu dong tai bao cao tren onebss.vnpt.vn.")
    return url


def report_url_title(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    query_text = parsed.fragment.split("?", 1)[1] if "?" in parsed.fragment else parsed.query
    query = parse_qs(query_text)
    name = query.get("name", [""])[0]
    if name:
        return unquote(name)
    path = query.get("path", [""])[0]
    return Path(unquote(path)).name if path else "onebss_report"


def safe_filename_part(value: Any, fallback: str = "onebss_report") -> str:
    text = str(value or "").strip() or fallback
    text = FILENAME_UNSAFE_CHARS.sub("_", text)
    text = re.sub(r"\s+", " ", text).strip(" ._")
    return text[:160] or fallback


def build_target_file_path(
    settings: Settings,
    schedule: dict[str, Any],
    *,
    suggested_filename: str = "",
    report_title: str = "",
) -> Path:
    suggested_ext = Path(suggested_filename or "").suffix or ".xlsx"
    template = safe_filename_part(
        schedule.get("file_name_template") or report_title or report_url_title(str(schedule.get("report_url") or "")),
    )
    template_path = Path(template)
    extension = template_path.suffix or suggested_ext
    stem = template_path.stem if template_path.suffix else template
    suffix = datetime.now(LOCAL_TIMEZONE).strftime("%H%M_%d%m%Y")
    filename = f"{safe_filename_part(stem)}_{suffix}{extension}"
    base_dir = Path(str(getattr(settings, "data_mining_download_dir", "data/data_mining_downloads") or "data/data_mining_downloads"))
    return (base_dir / filename).resolve()


def save_downloaded_file(settings: Settings, source_file: Path, storage_link: str) -> dict[str, Any]:
    target = str(storage_link or "").strip()
    folder_id = google_drive_folder_id(settings, target)
    if folder_id and (extract_google_drive_folder_id(target) or str(getattr(settings, "google_drive_folder_id", "") or "").strip()):
        try:
            uploaded = upload_file_to_google_drive(settings, source_file, source_file.name, folder_id)
        except GoogleDriveConfigurationError as error:
            return {
                "ok": False,
                "status": "google_drive_not_configured",
                "message": f"Da tai bao cao OneBSS va luu local, nhung Google Drive chua cau hinh dung: {error}",
                "storage_link": target,
                "storage_status": "google_drive_not_configured",
            }
        except Exception as error:
            logger.exception("Cannot upload %s to Google Drive folder %s", source_file, folder_id)
            return {
                "ok": False,
                "status": "google_drive_upload_failed",
                "message": f"Da tai bao cao OneBSS va luu local, nhung upload Google Drive loi: {str(error)[:300]}",
                "storage_link": target,
                "storage_status": "google_drive_upload_failed",
            }
        return {
            "ok": True,
            "message": "Da tai bao cao OneBSS va upload Google Drive.",
            "storage_link": uploaded.get("web_view_link") or uploaded.get("web_content_link") or target,
            "storage_status": f"uploaded_google_drive:{uploaded.get('file_id') or ''}",
        }
    return {
        "ok": True,
        "message": "Da tai bao cao OneBSS.",
        "storage_link": target,
        "storage_status": copy_to_storage_link(source_file, target),
    }


def copy_to_storage_link(source_file: Path, storage_link: str) -> str:
    target = str(storage_link or "").strip()
    if not target:
        return "saved_local"
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https"}:
        if "drive.google.com" in parsed.netloc.lower() or "docs.google.com" in parsed.netloc.lower():
            return "saved_local_google_drive_oauth_required"
        return "saved_local_external_upload_not_configured"
    target_path = Path(target).expanduser()
    if target_path.suffix:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_path)
    else:
        target_path.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_path / source_file.name)
    return "saved_local_and_copied"


REPORT_COMPONENT_READY_SCRIPT = """
() => {
  const stack = [document.body];
  const seen = new Set();
  while (stack.length) {
    const element = stack.pop();
    if (!element || seen.has(element)) continue;
    seen.add(element);
    const vm = element.__vue__;
    if (vm && typeof vm.DirectExport === 'function' && typeof vm.buildReportParams === 'function' && vm.current_node && vm.current_node.report_id) {
      return true;
    }
    for (const child of element.children || []) stack.push(child);
  }
  return false;
}
"""


EXPORT_DIRECT_SCRIPT = """
(overrides) => new Promise((resolve) => {
  function findReportVm() {
    const stack = [document.body];
    const seen = new Set();
    while (stack.length) {
      const element = stack.pop();
      if (!element || seen.has(element)) continue;
      seen.add(element);
      const vm = element.__vue__;
      if (vm && typeof vm.DirectExport === 'function' && typeof vm.buildReportParams === 'function') return vm;
      for (const child of element.children || []) stack.push(child);
    }
    return null;
  }
  const vm = findReportVm();
  if (!vm) {
    resolve({ ok: false, message: 'Khong tim thay bo xuat bao cao OneBSS.' });
    return;
  }
  const reportId = vm.current_node && vm.current_node.report_id ? vm.current_node.report_id : vm.report_id;
  if (!reportId) {
    resolve({ ok: false, message: 'Bao cao OneBSS chua co report_id.' });
    return;
  }
  const params = Object.assign({}, vm.buildReportParams ? vm.buildReportParams() : {}, overrides || {});
  Promise.resolve(vm.DirectExport(params, reportId))
    .then((ok) => resolve({
      ok: Boolean(ok),
      message: ok ? 'Da tao file xuat.' : 'OneBSS khong tao duoc file xuat.',
      report_id: reportId,
      title: vm.title || (vm.header && vm.header.title) || '',
      params,
    }))
    .catch((error) => resolve({
      ok: false,
      message: String((error && error.message) || error || 'Loi xuat bao cao OneBSS.'),
      report_id: reportId,
      title: vm.title || (vm.header && vm.header.title) || '',
      params,
    }));
})
"""
