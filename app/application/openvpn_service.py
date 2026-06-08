from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import shutil
import subprocess
import threading
import time
from typing import Any

from app.settings import Settings


class OpenVPNService:
    """Quan ly tunnel SSL VPN bang openconnect.

    Ten class giu lai de khong phai doi nhieu import cu, nhung service nay
    khong goi lenh `openvpn --config`. Fortinet/Cisco/Sophos SSL VPN can
    openconnect de bat tay HTTPS va tao tunnel he thong.
    """

    CONNECTED_MARKERS = (
        "connected as",
        "vpn established",
        "esp session established",
        "dtls session established",
        "configured as",
        "got addresses",
    )
    ERROR_MARKERS = ("login failed", "authentication failed", "unexpected 401", "failed to connect")

    def __init__(self) -> None:
        self.settings: Settings | None = None
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.log_tail: deque[str] = deque(maxlen=80)
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
            raise RuntimeError("SSL VPN service chua duoc configure.")
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_forever, name="ssl-vpn-openconnect", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self._terminate_process()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def status(self) -> dict[str, Any]:
        settings = self.settings
        with self.lock:
            configured = bool(settings and settings.vpn_host and settings.vpn_username and settings.vpn_password.get_secret_value())
            return {
                "enabled": configured,
                "configured": configured,
                "client": "openconnect",
                "protocol": settings.ssl_vpn_protocol if settings else "",
                "host": settings.vpn_host if settings else "",
                "port": settings.vpn_port if settings else 0,
                "connected": self.connected,
                "state": self.state,
                "pid": self.process.pid if self.process and self.process.poll() is None else None,
                "restarts": self.restarts,
                "started_at": self.started_at,
                "last_event": self.last_event,
                "last_error": self.last_error,
                "log_tail": list(self.log_tail),
                "binary": settings.ssl_vpn_binary if settings else "",
            }

    def _run_forever(self) -> None:
        assert self.settings is not None
        settings = self.settings
        if not settings.vpn_host:
            self._set_state("disabled", "Chua cau hinh VPN_HOST, tunnel nen khong khoi chay.")
            return
        if not settings.vpn_username or not settings.vpn_password.get_secret_value():
            self._set_state("disabled", "Chua cau hinh VPN_USERNAME hoac VPN_PASSWORD.")
            return

        while not self.stop_event.is_set():
            command = self._build_command()
            if not command:
                return
            self._set_state("connecting", "Dang khoi chay SSL VPN bang openconnect.")
            try:
                self.process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.started_at = datetime.now(UTC).isoformat()
                self._send_password()
                self._read_process_output()
            except OSError as error:
                self._set_state("error", f"Khong chay duoc lenh openconnect: {error}", str(error))
            finally:
                self.connected = False
                self._terminate_process()
                if not self.stop_event.is_set():
                    self.restarts += 1
                    self._set_state("reconnecting", "SSL VPN da dung, se tu ket noi lai.")
                    time.sleep(max(1, settings.ssl_vpn_restart_seconds))

    def _build_command(self) -> list[str] | None:
        assert self.settings is not None
        settings = self.settings
        binary = shutil.which(settings.ssl_vpn_binary)
        if not binary:
            self._set_state("error", "May chu chua cai openconnect hoac SSL_VPN_BINARY khong dung.")
            return None
        command = [
            binary,
            f"{settings.vpn_host}:{settings.vpn_port}",
            "--protocol",
            settings.ssl_vpn_protocol,
            "--user",
            settings.vpn_username,
            "--passwd-on-stdin",
            "--non-inter",
            "--reconnect-timeout",
            "30",
        ]
        if not settings.vpn_tls_verify:
            command.append("--no-cert-check")
        return command

    def _send_password(self) -> None:
        assert self.settings is not None
        if not self.process or not self.process.stdin:
            return
        try:
            self.process.stdin.write(f"{self.settings.vpn_password.get_secret_value()}\n")
            self.process.stdin.flush()
            self.process.stdin.close()
        except OSError as error:
            self._set_state("error", "Khong gui duoc mat khau vao openconnect.", str(error))

    def _read_process_output(self) -> None:
        process = self.process
        if not process or not process.stdout:
            return
        for line in process.stdout:
            if self.stop_event.is_set():
                break
            clean = line.strip()
            lower = clean.lower()
            if clean:
                with self.lock:
                    self.log_tail.append(clean)
                    self.last_event = clean
            if any(marker in lower for marker in self.CONNECTED_MARKERS):
                self.connected = True
                self._set_state("connected", "SSL VPN connected.")
            if any(marker in lower for marker in self.ERROR_MARKERS):
                self.connected = False
                self._set_state("error", "SSL VPN xac thuc hoac bat tay that bai.", clean)
        exit_code = process.poll()
        if exit_code not in (None, 0):
            self._set_state("error", f"openconnect thoat voi ma {exit_code}.", f"exit_code={exit_code}")

    def _terminate_process(self) -> None:
        process = self.process
        if not process or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    def _set_state(self, state: str, event: str, error: str = "") -> None:
        with self.lock:
            self.state = state
            self.last_event = event
            self.last_error = error
            if event:
                self.log_tail.append(event)


openvpn_service = OpenVPNService()
