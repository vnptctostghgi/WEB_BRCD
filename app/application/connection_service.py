from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
from typing import Any

import httpx

from app.application.database_service import DatabaseService
from app.application.openvpn_service import openvpn_service
from app.application.telegram_notifier import TelegramNotifier
from app.data_access.oracle_repository import OracleRepository
from app.settings import Settings


class ConnectionService:
    def __init__(self, repository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def seed_current_connections(self) -> None:
        self.repository.upsert_system_connection(
            code="oracle_agency_db",
            name="DB cơ quan Oracle",
            connection_type="oracle",
            description="Nguồn dữ liệu nghiệp vụ BRCĐ của đơn vị, tài khoản chỉ đọc.",
            config={
                "host": self.settings.db_host,
                "port": self.settings.db_port,
                "service": self.settings.db_service,
                "user": self.settings.db_user,
                "secret_ref": "DB_PASS",
            },
            is_active=not self.settings.db_mock_mode,
        )
        self.repository.upsert_system_connection(
            code="supabase_web_db",
            name="DB của web Supabase",
            connection_type="supabase",
            description="Database chính của ứng dụng quản trị web.",
            config={
                "rest_url": self.settings.supabase_rest_url,
                "backend": self.settings.app_database_backend,
                "secret_ref": "SUPABASE_SECRET_KEY",
            },
            is_active=self.settings.app_database_backend == "supabase",
        )
        self.repository.upsert_system_connection(
            code="agency_ssl_vpn",
            name="VPN OpenVPN cơ quan",
            connection_type="vpn_ssl",
            description="Kết nối OpenVPN SSL/TLS trước khi truy cập FTP và Database nội bộ.",
            config={
                "host": self.settings.vpn_host or "14.241.183.190",
                "port": self.settings.vpn_port or 4443,
                "username": self.settings.vpn_username or "quyennt.cto",
                "type": "OpenVPN SSL/TLS",
                "openvpn_binary": self.settings.openvpn_binary,
                "openvpn_config_path": self.settings.openvpn_config_path,
                "test_targets": self._parse_targets(self.settings.vpn_test_targets) or [
                    {"host": self.settings.db_host or "10.92.53.53", "port": self.settings.db_port or 1521, "name": "Oracle DB cơ quan"},
                ],
                "secret_ref": "VPN_PASSWORD",
            },
            is_active=True,
        )
        self.repository.upsert_system_connection(
            code="ftp_storage",
            name="FTP",
            connection_type="ftp",
            description="Kết nối FTP phục vụ trao đổi file. Chưa cấu hình thông tin máy chủ.",
            config={"host": "", "port": 21, "secret_ref": "FTP_PASSWORD"},
            is_active=False,
        )
        self.repository.upsert_system_connection(
            code="drive_storage",
            name="Drive",
            connection_type="drive",
            description="Kết nối Drive/Cloud storage. Chưa cấu hình OAuth hoặc service account.",
            config={"provider": "", "folder": "", "secret_ref": "DRIVE_SECRET"},
            is_active=False,
        )
        self.repository.upsert_system_connection(
            code="telegram_bot",
            name="Telegram Bot cảnh báo",
            connection_type="telegram",
            description="Gửi cảnh báo khi web lỗi hoặc mất kết nối hệ thống.",
            config={
                "bot_username": self.settings.bot_username,
                "chat_id": self.settings.my_telegram_id,
                "secret_ref": "TELEGRAM_TOKEN",
            },
            is_active=bool(self.settings.telegram_token.get_secret_value() and self.settings.my_telegram_id),
        )

    def test_connection(self, code: str) -> dict[str, Any]:
        connection = self.repository.get_system_connection_by_code(code)
        if not connection:
            raise ValueError("Không tìm thấy kết nối.")

        if connection["connection_type"] == "oracle":
            result = DatabaseService(OracleRepository(self.settings)).get_connection_status()
            return self._with_connection(result, connection)

        if connection["connection_type"] == "supabase":
            return self._with_connection(self._test_supabase(), connection)

        if connection["connection_type"] == "telegram":
            return self._with_connection(TelegramNotifier(self.settings).test(), connection)

        if connection["connection_type"] == "vpn_ssl":
            return self._with_connection(self._test_vpn_ssl(connection), connection)

        return self._with_connection(
            {
                "ok": False,
                "message": f"{connection['name']} chưa có đủ cấu hình để kiểm tra.",
                "details": {"type": connection["connection_type"]},
            },
            connection,
        )

    def _test_supabase(self) -> dict[str, Any]:
        if not self.settings.supabase_rest_url or not self.settings.supabase_secret_key.get_secret_value():
            return {"ok": False, "message": "Chưa cấu hình URL hoặc secret key Supabase.", "details": None}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get(
                    f"{self.settings.supabase_rest_url.rstrip('/')}/features",
                    params={"select": "code", "limit": "1"},
                    headers={"apikey": self.settings.supabase_secret_key.get_secret_value()},
                )
            if response.status_code < 400:
                return {
                    "ok": True,
                    "message": "Kết nối Supabase thành công.",
                    "details": {"status_code": response.status_code},
                }
            return {
                "ok": False,
                "message": self._supabase_error_message(response.status_code),
                "details": {"status_code": response.status_code},
            }
        except httpx.TimeoutException:
            return {"ok": False, "message": "Supabase phản hồi quá lâu.", "details": None}
        except httpx.RequestError:
            return {"ok": False, "message": "Không kết nối được Supabase REST API.", "details": None}

    @staticmethod
    def _supabase_error_message(status_code: int) -> str:
        if status_code in {401, 403}:
            return "Supabase từ chối truy cập. Kiểm tra lại secret key."
        if status_code == 404:
            return "Không tìm thấy bảng hoặc endpoint Supabase."
        if status_code >= 500:
            return "Supabase đang lỗi máy chủ."
        return f"Supabase trả lỗi HTTP {status_code}."

    def _test_vpn_ssl(self, connection: dict[str, Any]) -> dict[str, Any]:
        config = connection.get("config", {})
        host = config.get("host")
        port = int(config.get("port", 4443))
        if not host:
            return {"ok": False, "message": "Chưa cấu hình host VPN.", "details": None}

        base_details = {
            "host": host,
            "port": port,
            "username": config.get("username"),
            "type": config.get("type", "OpenVPN SSL/TLS"),
        }

        config_path = config.get("openvpn_config_path") or self.settings.openvpn_config_path
        if config_path:
            vpn_status = openvpn_service.status()
            targets = config.get("test_targets") or self._parse_targets(self.settings.vpn_test_targets)
            route_results = self._test_targets(targets) if vpn_status.get("connected") else []
            all_routes_ok = all(item["ok"] for item in route_results) if route_results else bool(vpn_status.get("connected"))
            return {
                "ok": bool(vpn_status.get("connected") and all_routes_ok),
                "message": "OpenVPN nen dang ket noi va tuyen noi bo san sang." if vpn_status.get("connected") and all_routes_ok else "OpenVPN nen chua san sang. Xem chi tiet log de kiem tra cau hinh, quyen TUN/TAP hoac route DB/FTP.",
                "details": {**base_details, "stage": "persistent_openvpn_status", "vpn": vpn_status, "targets": route_results},
            }

        try:
            with socket.create_connection((host, port), timeout=8) as tcp_socket:
                tcp_socket.settimeout(8)
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                try:
                    with context.wrap_socket(tcp_socket, server_hostname=host) as tls_socket:
                        return {
                            "ok": True,
                            "message": f"VPN SSL phản hồi tốt. TCP và SSL handshake thành công tới {host}:{port}.",
                            "details": {
                                **base_details,
                                "tls_version": tls_socket.version(),
                                "cipher": tls_socket.cipher()[0] if tls_socket.cipher() else None,
                            },
                        }
                except ssl.SSLError as error:
                    return {
                        "ok": False,
                        "message": "Đã mở được cổng VPN nhưng bắt tay SSL thất bại. Kiểm tra chứng chỉ, giao thức SSL/TLS hoặc thiết bị VPN.",
                        "details": {**base_details, "stage": "ssl_handshake", "error": str(error)},
                    }
        except TimeoutError as error:
            return {
                "ok": False,
                "message": "Không kết nối được VPN: máy chủ phản hồi quá lâu hoặc đường mạng/VPN bị chặn.",
                "details": {**base_details, "stage": "tcp_connect", "error": str(error)},
            }
        except OSError as error:
            return {
                "ok": False,
                "message": "Không kết nối được cổng OpenVPN. Kiểm tra IP, cổng 4443, firewall hoặc trạng thái thiết bị VPN.",
                "details": {**base_details, "stage": "tcp_connect", "error": str(error)},
            }

    def _test_openvpn_tunnel(self, config: dict[str, Any], base_details: dict[str, Any]) -> dict[str, Any] | None:
        config_path = config.get("openvpn_config_path") or self.settings.openvpn_config_path
        binary_name = config.get("openvpn_binary") or self.settings.openvpn_binary or "openvpn"
        username = config.get("username") or self.settings.vpn_username
        password = self.settings.vpn_password.get_secret_value()
        targets = config.get("test_targets") or self._parse_targets(self.settings.vpn_test_targets)

        if not config_path:
            return {
                "ok": False,
                "message": "Chưa có file cấu hình OpenVPN (.ovpn) trên máy chủ web nên chưa thể khởi chạy tunnel.",
                "details": {**base_details, "stage": "openvpn_config", "required": "OPENVPN_CONFIG_PATH hoặc config.openvpn_config_path"},
            }
        if not Path(config_path).exists():
            return {
                "ok": False,
                "message": "Không tìm thấy file cấu hình OpenVPN trên máy chủ web.",
                "details": {**base_details, "stage": "openvpn_config", "openvpn_config_path": config_path},
            }
        binary = shutil.which(binary_name) or (binary_name if Path(binary_name).exists() else None)
        if not binary:
            return {
                "ok": False,
                "message": "Máy chủ web chưa cài OpenVPN CLI nên không thể mở tunnel từ backend.",
                "details": {**base_details, "stage": "openvpn_binary", "openvpn_binary": binary_name},
            }
        if not username or not password:
            return {
                "ok": False,
                "message": "Chưa cấu hình tài khoản hoặc mật khẩu OpenVPN trong biến môi trường.",
                "details": {**base_details, "stage": "openvpn_auth", "required": "VPN_USERNAME và VPN_PASSWORD"},
            }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as auth_file:
            auth_file.write(f"{username}\n{password}\n")
            auth_path = auth_file.name
        command = [
            binary,
            "--config", config_path,
            "--auth-user-pass", auth_path,
            "--connect-retry-max", "1",
            "--verb", "3",
            "--pull-filter", "ignore", "redirect-gateway",
        ]
        process: subprocess.Popen | None = None
        log_lines: list[str] = []
        started_at = time.time()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            while time.time() - started_at < 30:
                line = process.stdout.readline()
                if line:
                    clean = self._redact_secret(line.strip(), password)
                    log_lines.append(clean)
                    if "Initialization Sequence Completed" in line:
                        route_results = self._test_targets(targets)
                        all_ok = all(item["ok"] for item in route_results) if route_results else True
                        return {
                            "ok": all_ok,
                            "message": "OpenVPN đã kết nối. Kiểm tra tuyến nội bộ thành công." if all_ok else "OpenVPN đã kết nối nhưng tuyến tới DB/FTP còn lỗi.",
                            "details": {**base_details, "stage": "route_test", "targets": route_results, "log_tail": log_lines[-30:]},
                        }
                if process.poll() is not None:
                    break
            return {
                "ok": False,
                "message": "OpenVPN chưa kết nối thành công trong thời gian kiểm tra.",
                "details": {**base_details, "stage": "openvpn_connect", "exit_code": process.poll(), "log_tail": log_lines[-50:]},
            }
        except OSError as error:
            return {
                "ok": False,
                "message": "Không chạy được lệnh OpenVPN trên máy chủ web.",
                "details": {**base_details, "stage": "openvpn_spawn", "error": str(error), "command": command[:2]},
            }
        finally:
            try:
                Path(auth_path).unlink(missing_ok=True)
            except OSError:
                pass
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

    @staticmethod
    def _redact_secret(value: str, secret: str) -> str:
        return value.replace(secret, "***") if secret else value

    @staticmethod
    def _parse_targets(raw_targets: str) -> list[dict[str, Any]]:
        targets = []
        for item in (raw_targets or "").split(","):
            value = item.strip()
            if not value or ":" not in value:
                continue
            host, port_text = value.rsplit(":", 1)
            try:
                targets.append({"host": host.strip(), "port": int(port_text), "name": value})
            except ValueError:
                continue
        return targets

    @staticmethod
    def _test_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for target in targets:
            host = target.get("host")
            port = int(target.get("port", 0))
            try:
                with socket.create_connection((host, port), timeout=8):
                    results.append({"ok": True, "name": target.get("name"), "host": host, "port": port, "message": "Kết nối được."})
            except OSError as error:
                results.append({"ok": False, "name": target.get("name"), "host": host, "port": port, "message": str(error)})
        return results

    def _legacy_vpn_http_probe(self, host: str, port: int) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=10, verify=False) as client:
                response = client.get(f"https://{host}:{port}")
            return {
                "ok": response.status_code < 500,
                "message": f"VPN phan hoi HTTP {response.status_code}. Cong VPN co phan hoi.",
                "details": {"status_code": response.status_code},
            }
        except httpx.TimeoutException:
            return {"ok": False, "message": "VPN phan hoi qua lau hoac bi chan.", "details": {"host": host, "port": port}}
        except httpx.RequestError:
            return {"ok": False, "message": "Khong ket noi duoc cong VPN SSL.", "details": {"host": host, "port": port}}

    @staticmethod
    def _with_connection(result: dict[str, Any], connection: dict[str, Any]) -> dict[str, Any]:
        result["connection_code"] = connection["code"]
        result["connection_name"] = connection["name"]
        return result
