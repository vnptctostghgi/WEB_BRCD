from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
