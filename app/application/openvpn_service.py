from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any

from app.settings import Settings


class OpenVPNService:
    """Quan ly tien trinh OpenVPN chay nen trong suot vong doi web server."""

    def __init__(self) -> None:
        self.settings: Settings | None = None
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.log_tail: deque[str] = deque(maxlen=80)
        self.auth_file_to_cleanup: str | None = None
        self.state = "not_started"
        self.connected = False
        self.restarts = 0
        self.started_at: str | None = None
        self.last_event = ""
        self.last_error = ""

    def configure(self, settings: Settings) -> None:
        self.settings = settings

    def start(self) -> None:
        if not self.settings:
            raise RuntimeError("OpenVPNService chua duoc configure.")
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_forever, name="openvpn-service", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self._terminate_process()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        self._cleanup_auth_file()

    def status(self) -> dict[str, Any]:
        settings = self.settings
        with self.lock:
            configured = bool(settings and settings.openvpn_config_path)
            return {
                "enabled": configured,
                "configured": configured,
                "connected": self.connected,
                "state": self.state,
                "pid": self.process.pid if self.process and self.process.poll() is None else None,
                "restarts": self.restarts,
                "started_at": self.started_at,
                "last_event": self.last_event,
                "last_error": self.last_error,
                "log_tail": list(self.log_tail),
                "config_path": settings.openvpn_config_path if settings else "",
                "binary": settings.openvpn_binary if settings else "",
            }

    def _run_forever(self) -> None:
        assert self.settings is not None
        settings = self.settings
        if not settings.openvpn_config_path:
            self._set_state("disabled", "Chua cau hinh OPENVPN_CONFIG_PATH, tunnel nen khong khoi chay.")
            return
        if not Path(settings.openvpn_config_path).exists():
            self._set_state("error", "Khong tim thay file .ovpn.")
            return

        while not self.stop_event.is_set():
            command = self._build_command()
            if not command:
                return
            self._set_state("connecting", "Dang khoi chay OpenVPN.")
            try:
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.started_at = datetime.now(UTC).isoformat()
                self._read_process_output()
            except OSError as error:
                self._set_state("error", f"Khong chay duoc lenh OpenVPN: {error}", str(error))
            finally:
                self.connected = False
                self._terminate_process()
                if not self.stop_event.is_set():
                    self.restarts += 1
                    self._set_state("reconnecting", "OpenVPN da dung, se tu ket noi lai.")
                    time.sleep(max(1, settings.openvpn_restart_seconds))

    def _build_command(self) -> list[str] | None:
        assert self.settings is not None
        settings = self.settings
        binary = shutil.which(settings.openvpn_binary) or (
            settings.openvpn_binary if Path(settings.openvpn_binary).exists() else None
        )
        if not binary:
            self._set_state("error", "May chu chua cai OpenVPN CLI hoac OPENVPN_BINARY khong dung.")
            return None
        auth_path = self._get_auth_file()
        if not auth_path:
            return None
        return [
            binary,
            "--config",
            settings.openvpn_config_path,
            "--auth-user-pass",
            auth_path,
            "--connect-retry",
            "5",
            "30",
            "--resolv-retry",
            "infinite",
            "--keepalive",
            "10",
            "60",
            "--verb",
            "3",
        ]

    def _get_auth_file(self) -> str | None:
        assert self.settings is not None
        settings = self.settings
        if settings.openvpn_auth_file_path:
            if Path(settings.openvpn_auth_file_path).exists():
                return settings.openvpn_auth_file_path
            self._set_state("error", "OPENVPN_AUTH_FILE_PATH khong ton tai.")
            return None
        username = settings.vpn_username
        password = settings.vpn_password.get_secret_value()
        if not username or not password:
            self._set_state("error", "Thieu VPN_USERNAME hoac VPN_PASSWORD.")
            return None
        auth_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        auth_file.write(f"{username}\n{password}\n")
        auth_file.close()
        self.auth_file_to_cleanup = auth_file.name
        return auth_file.name

    def _read_process_output(self) -> None:
        process = self.process
        if not process or not process.stdout:
            return
        for line in process.stdout:
            if self.stop_event.is_set():
                break
            clean = line.strip()
            if clean:
                with self.lock:
                    self.log_tail.append(clean)
                    self.last_event = clean
            if "Initialization Sequence Completed" in clean:
                self.connected = True
                self._set_state("connected", "OpenVPN connected.")
            if "AUTH_FAILED" in clean:
                self.connected = False
                self._set_state("error", "OpenVPN xac thuc that bai.", clean)
        exit_code = process.poll()
        if exit_code not in (None, 0):
            self._set_state("error", f"OpenVPN thoat voi ma {exit_code}.", f"exit_code={exit_code}")

    def _terminate_process(self) -> None:
        process = self.process
        if not process or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    def _cleanup_auth_file(self) -> None:
        if not self.auth_file_to_cleanup:
            return
        try:
            Path(self.auth_file_to_cleanup).unlink(missing_ok=True)
        except OSError:
            pass
        self.auth_file_to_cleanup = None

    def _set_state(self, state: str, event: str, error: str = "") -> None:
        with self.lock:
            self.state = state
            self.last_event = event
            self.last_error = error
            if event:
                self.log_tail.append(event)


openvpn_service = OpenVPNService()
