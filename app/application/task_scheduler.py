from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.zalo_auto_message_service import send_zalo_auto_message
from app.application.database_service import DatabaseService
from app.data_access.internal_api_client import InternalApiClient
from app.application.telegram_notifier import TelegramNotifier
from app.settings import Settings


logger = logging.getLogger(__name__)
try:
    LOCAL_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
except ZoneInfoNotFoundError:
    LOCAL_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


class WorkTaskScheduler:
    """Gui nhac viec Telegram theo lich, chi tat khi admin xac nhan hoan thanh."""

    def __init__(self) -> None:
        self.repository: Any | None = None
        self.settings: Settings | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.interval_seconds = 30
        self.schema_warning_logged = False

    def configure(self, repository: Any, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def start(self) -> None:
        if not self.repository or not self.settings:
            raise RuntimeError("WorkTaskScheduler chua duoc configure.")
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, name="work-task-scheduler", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.check_due_tasks()
            except Exception:
                logger.exception("Work task scheduler failed")
            self.stop_event.wait(self.interval_seconds)

    def check_due_tasks(self, now: datetime | None = None) -> int:
        assert self.repository is not None
        assert self.settings is not None
        current = now or datetime.now(LOCAL_TIMEZONE)
        sent_count = 0
        try:
            tasks = self.repository.list_work_tasks(include_completed=False)
        except RuntimeError as error:
            if "work_tasks" in str(error) and not self.schema_warning_logged:
                logger.warning("Bang work_tasks chua ton tai. Hay chay sql/supabase_upgrade_admin_modules.sql tren Supabase.")
                self.schema_warning_logged = True
            return 0
        for task in tasks:
            if not self._is_due(task, current):
                continue
            if TelegramNotifier(self.settings).send_task_reminder(task):
                self.repository.mark_work_task_notified(task["task_id"], current.date().isoformat())
                sent_count += 1
        return sent_count

    @staticmethod
    def _is_due(task: dict[str, Any], current: datetime) -> bool:
        if not task.get("is_active") or task.get("check"):
            return False
        run_time = str(task.get("time") or "").strip()
        if run_time != current.strftime("%H:%M"):
            return False
        today = current.date().isoformat()
        if task.get("last_notified_date") == today:
            return False
        schedule_type = str(task.get("type") or "Daily").strip().lower()
        if schedule_type == "daily":
            return True
        if schedule_type == "once":
            return str(task.get("once_date") or "") == today
        if schedule_type == "weekly":
            return WorkTaskScheduler._weekday_matches(task.get("weekday"), current.weekday())
        return False

    @staticmethod
    def _weekday_matches(raw_weekday: Any, weekday_index: int) -> bool:
        if raw_weekday in (None, ""):
            return False
        value = str(raw_weekday).strip().lower()
        aliases = {
            "0": 0, "2": 0, "mon": 0, "monday": 0, "thu 2": 0, "t2": 0,
            "1": 1, "3": 1, "tue": 1, "tuesday": 1, "thu 3": 1, "t3": 1,
            "4": 2, "wed": 2, "wednesday": 2, "thu 4": 2, "t4": 2,
            "5": 3, "thu": 3, "thursday": 3, "thu 5": 3, "t5": 3,
            "6": 4, "fri": 4, "friday": 4, "thu 6": 4, "t6": 4,
            "7": 5, "sat": 5, "saturday": 5, "thu 7": 5, "t7": 5,
            "cn": 6, "sun": 6, "sunday": 6, "chu nhat": 6,
        }
        return aliases.get(value) == weekday_index


work_task_scheduler = WorkTaskScheduler()


class DashboardChartCacheScheduler:
    """Refresh cached dashboard chart payloads on the existing web service."""

    def __init__(self) -> None:
        self.repository: Any | None = None
        self.settings: Settings | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.initial_delay_seconds = 20

    def configure(self, repository: Any, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def start(self) -> None:
        if not self.repository or not self.settings:
            raise RuntimeError("DashboardChartCacheScheduler chua duoc configure.")
        if not getattr(self.settings, "dashboard_chart_cache_auto_refresh_enabled", False):
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, name="dashboard-chart-cache-scheduler", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def _run_loop(self) -> None:
        if self.stop_event.wait(self.initial_delay_seconds):
            return
        while not self.stop_event.is_set():
            try:
                result = self.refresh_once()
                logger.info(
                    "Dashboard chart cache refresh finished: refreshed=%s failed=%s skipped=%s",
                    result.get("refreshed"),
                    result.get("failed"),
                    result.get("skipped"),
                )
            except Exception:
                logger.exception("Dashboard chart cache scheduler failed")
            interval = int(getattr(self.settings, "dashboard_chart_cache_refresh_interval_seconds", 300) or 300)
            self.stop_event.wait(max(60, interval))

    def refresh_once(self) -> dict[str, Any]:
        assert self.repository is not None
        assert self.settings is not None
        service = DatabaseService(InternalApiClient(self.settings), self.repository)
        return service.refresh_dashboard_chart_cache()


dashboard_chart_cache_scheduler = DashboardChartCacheScheduler()


class ZaloAutoMessageScheduler:
    """Gui anh/tin Zalo tu dong theo cau hinh trong admin."""

    def __init__(self) -> None:
        self.repository: Any | None = None
        self.settings: Settings | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.interval_seconds = 30
        self.schema_warning_logged = False

    def configure(self, repository: Any, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def start(self) -> None:
        if not self.repository or not self.settings:
            raise RuntimeError("ZaloAutoMessageScheduler chua duoc configure.")
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, name="zalo-auto-message-scheduler", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.check_due_messages()
            except Exception:
                logger.exception("Zalo auto message scheduler failed")
            self.stop_event.wait(self.interval_seconds)

    def check_due_messages(self, now: datetime | None = None) -> int:
        assert self.repository is not None
        assert self.settings is not None
        current = now or datetime.now(LOCAL_TIMEZONE)
        sent_count = 0
        try:
            schedules = self.repository.list_zalo_auto_messages(active_only=True)
        except RuntimeError as error:
            if "zalo_auto_messages" in str(error) and not self.schema_warning_logged:
                logger.warning("Bang zalo_auto_messages chua ton tai. Hay chay sql/supabase_upgrade_admin_modules.sql tren Supabase.")
                self.schema_warning_logged = True
            return 0
        for schedule in schedules:
            run_key = self._due_run_key(schedule, current)
            if not run_key:
                continue
            result = send_zalo_auto_message(self.repository, self.settings, schedule)
            self.repository.mark_zalo_auto_message_run(
                str(schedule.get("schedule_id") or ""),
                run_key,
                bool(result.get("ok")),
                "" if result.get("ok") else str(result.get("message") or ""),
            )
            if result.get("ok"):
                sent_count += 1
        return sent_count

    @classmethod
    def _due_run_key(cls, schedule: dict[str, Any], current: datetime) -> str:
        if not schedule.get("is_active"):
            return ""
        schedule_type = str(schedule.get("schedule_type") or "Daily").strip().lower()
        current_time = current.strftime("%H:%M")
        run_key = ""
        if schedule_type in {"timewindow", "time_window", "window"}:
            slots = {str(slot or "").strip()[:5] for slot in (schedule.get("time_slots") or []) if str(slot or "").strip()}
            if current_time in slots:
                run_key = f"{current.date().isoformat()}:{current_time}"
        elif schedule_type == "daily":
            if current_time == str(schedule.get("run_time") or "07:00")[:5]:
                run_key = current.date().isoformat()
        elif schedule_type == "weekly":
            if current_time == str(schedule.get("run_time") or "07:00")[:5] and WorkTaskScheduler._weekday_matches(schedule.get("weekday"), current.weekday()):
                iso_year, iso_week, _ = current.isocalendar()
                run_key = f"{iso_year}-W{iso_week:02d}-{current.weekday()}"
        elif schedule_type == "monthly":
            month_day = cls._safe_month_day(schedule.get("month_day"), current)
            if current_time == str(schedule.get("run_time") or "07:00")[:5] and current.day == month_day:
                run_key = current.strftime("%Y-%m")
        if not run_key or schedule.get("last_run_key") == run_key:
            return ""
        return run_key

    @staticmethod
    def _safe_month_day(raw_day: Any, current: datetime) -> int:
        try:
            day = int(raw_day or 1)
        except (TypeError, ValueError):
            day = 1
        last_day = calendar.monthrange(current.year, current.month)[1]
        return min(max(day, 1), last_day)


zalo_auto_message_scheduler = ZaloAutoMessageScheduler()
