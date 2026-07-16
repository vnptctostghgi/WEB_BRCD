import os
import json
import threading
import time
from io import BytesIO
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

os.environ["DB_MOCK_MODE"] = "true"
os.environ["INTERNAL_API_MOCK_MODE"] = "true"
os.environ["INTERNAL_API_URL"] = "http://10.92.17.88:8000/api/du-lieu-web"
os.environ["INTERNAL_API_TOKEN"] = "test-worker-token"
os.environ["APP_DATABASE_BACKEND"] = "sqlite"
os.environ["APP_DATABASE_PATH"] = "data/test_app.db"
os.environ["INITIAL_ADMIN_USERNAME"] = "admin"
os.environ["INITIAL_ADMIN_PASSWORD"] = "Admin@Brcd2026!"

test_database = Path("data/test_app.db")
test_database.unlink(missing_ok=True)

from fastapi.testclient import TestClient

from app.application.telegram_notifier import sanitize_alert_details, sanitize_alert_text
from app.application.database_service import DatabaseService
from app.data_access.supabase_repository import SupabaseRepository
from app.main import app
from app.presentation import routes
from app.settings import Settings, get_settings


def login(client: TestClient, username: str = "admin", password: str = "Admin@Brcd2026!") -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_unauthenticated_user_is_redirected_to_login() -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_login_uses_optimized_static_assets() -> None:
    with TestClient(app) as client:
        response = client.get("/login")
        assert response.status_code == 200
        assert "/static/tailwind-built.css?v=1" in response.text
        assert "cdn.tailwindcss.com" not in response.text
        assert "/static/login-hero-900.webp" in response.text
        assert "/static/images/system-logo-96.webp" in response.text


def test_admin_can_login_and_open_dashboard() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.get("/")
        assert response.status_code == 200
        assert 'rel="icon" type="image/png" href="/static/images/system-logo.png"' in response.text
        assert "/static/tailwind-built.css?v=1" in response.text
        assert "cdn.tailwindcss.com" not in response.text
        assert "dashboard-tab-fiber" not in response.text
        assert "Truy vấn SQL" in response.text
        assert "Báo cáo mới" in response.text
        assert "Quản trị người dùng" in response.text


def test_feature_path_opens_current_app_shell() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.get("/quantrimenu")
        assert response.status_code == 200
        assert 'data-feature-code="quantrimenu"' in response.text


def test_favicon_redirects_to_system_logo() -> None:
    with TestClient(app) as client:
        response = client.get("/favicon.ico", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/images/system-logo.png"


def test_static_assets_are_cacheable() -> None:
    with TestClient(app) as client:
        response = client.get("/static/app.js?v=53")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "SAMEORIGIN"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_mobile_gateway_admin_lists_are_clamped_to_twenty_rows() -> None:
    with TestClient(app) as client:
        login(client)
        sms = client.get("/api/admin/mobile-gateway/sms?page=1&page_size=100")
        notifications = client.get("/api/admin/mobile-gateway/notifications?page=1&page_size=100")
        commands = client.get("/api/admin/mobile-gateway/commands?limit=100")
        assert sms.status_code == 200
        assert notifications.status_code == 200
        assert commands.status_code == 200
        assert sms.json()["page_size"] == 20
        assert notifications.json()["page_size"] == 20
        assert len(commands.json()["commands"]) <= 20


def test_production_startup_validation_rejects_unsafe_defaults() -> None:
    settings = Settings(
        app_env="production",
        session_secret="change-this-session-secret",
        initial_admin_password="ChangeMe123!",
        internal_api_mock_mode=True,
    )
    with pytest.raises(RuntimeError) as error:
        settings.validate_for_startup()
    message = str(error.value)
    assert "SESSION_SECRET" in message
    assert "INITIAL_ADMIN_PASSWORD" in message
    assert "INTERNAL_API_MOCK_MODE" in message
    assert "ChangeMe123" not in message


def test_telegram_alert_sanitizer_redacts_secrets() -> None:
    text = sanitize_alert_text("token=abc123 password:super-secret cookie=session-id")
    assert "abc123" not in text
    assert "super-secret" not in text
    assert "session-id" not in text
    assert "[redacted]" in text

    details = sanitize_alert_details({"telegram_token": "abc123", "url": "/x?password=super-secret"})
    assert details["telegram_token"] == "[redacted]"
    assert "super-secret" not in details["url"]


def test_admin_navigation_payload_combines_features_and_layouts() -> None:
    with TestClient(app) as client:
        assert client.get("/api/navigation").status_code == 401
        login(client)
        response = client.get("/api/navigation")
        assert response.status_code == 200
        payload = response.json()
        assert any(feature["code"] == "quantrimenu" for feature in payload["features"])
        assert any(layout["page_id"] == "DASHBOARD_KINH_DOANH" for layout in payload["dashboard_layouts"])


def test_viewer_navigation_includes_parent_for_granted_child_dashboard() -> None:
    with TestClient(app) as client:
        login(client)
        saved = client.post(
            "/api/admin/dashboard-layouts",
            json={
                "page_id": "DASHBOARD_VIEWER_CHILD",
                "page_name": "Dashboard Viewer Child",
                "parent_code": "baocaomoi",
                "layout": {
                    "tabs": [
                        {
                            "tab_id": "tab_a",
                            "tab_name": "Tab A",
                            "order": 1,
                            "grid_layout": [
                                {
                                    "row_id": 1,
                                    "layout_type": "1_column",
                                    "widgets": [
                                        {
                                            "position": 1,
                                            "type": "text_title",
                                            "title": "Viewer dashboard",
                                            "text_content": "Only granted viewer can see this item.",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
        )
        assert saved.status_code == 200
        feature_code = saved.json()["feature_code"]
        created = client.post(
            "/api/admin/users",
            json={
                "username": "viewer_navigation",
                "full_name": "Viewer Navigation",
                "password": "Viewer@Navigation123",
                "role": "viewer",
            },
        )
        assert created.status_code == 200
        viewer_id = created.json()["user"]["id"]
        assert client.put(
            f"/api/admin/users/{viewer_id}/permissions",
            json={"feature_codes": [feature_code]},
        ).status_code == 200

        client.post("/api/auth/logout")
        login(client, "viewer_navigation", "Viewer@Navigation123")
        response = client.get("/api/navigation")
        assert response.status_code == 200
        payload = response.json()
        feature_codes = {feature["code"] for feature in payload["features"]}
        assert "baocaomoi" in feature_codes
        assert feature_code in feature_codes
        assert "quantriweb" not in feature_codes
        assert [layout["page_id"] for layout in payload["dashboard_layouts"]] == ["DASHBOARD_VIEWER_CHILD"]

        detail = client.get("/api/dashboard-layouts/DASHBOARD_VIEWER_CHILD")
        assert detail.status_code == 200
        assert detail.json()["feature_code"] == feature_code
        tab_data = client.get("/api/dashboard-layouts/DASHBOARD_VIEWER_CHILD/tabs/tab_a/data")
        assert tab_data.status_code == 200
        assert client.get("/api/dashboard-layouts/DASHBOARD_KINH_DOANH").status_code == 403


def test_five_failed_logins_send_telegram_alert(monkeypatch) -> None:
    sent_messages = []
    routes.FAILED_LOGIN_COUNTS.clear()

    def fake_send_message(self, title, message, details=None):
        sent_messages.append((title, message, details))
        return True

    monkeypatch.setattr("app.presentation.routes.TelegramNotifier.send_message", fake_send_message)
    with TestClient(app) as client:
        for _ in range(4):
            response = client.post("/api/auth/login", json={"username": "bad_admin", "password": "wrong"})
            assert response.status_code == 401
        assert sent_messages == []
        response = client.post("/api/auth/login", json={"username": "bad_admin", "password": "wrong"})
        assert response.status_code == 401
        assert len(sent_messages) == 1
        assert sent_messages[0][0] == "Canh bao dang nhap sai"
        response = client.post("/api/auth/login", json={"username": "bad_admin", "password": "wrong"})
        assert response.status_code == 401
        assert len(sent_messages) == 2


def test_telegram_alert_test_route_requires_admin(monkeypatch) -> None:
    sent_messages = []

    def fake_send_message(self, title, message, details=None):
        sent_messages.append((title, message, details))
        return True

    monkeypatch.setattr("app.presentation.routes.TelegramNotifier.send_message", fake_send_message)
    with TestClient(app) as client:
        response = client.get("/api/test/telegram-alert")
        assert response.status_code == 401
        assert sent_messages == []

        login(client)
        response = client.get("/api/test/telegram-alert")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert sent_messages[0][0] == "TEST Telegram"
        assert "[TEST]" in sent_messages[0][1]
        assert sent_messages[0][2]["actor"] == "admin"


def test_user_import_rejects_large_file() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.post(
            "/api/admin/users/import",
            files={
                "file": (
                    "users.xlsx",
                    b"x" * (routes.MAX_USER_IMPORT_BYTES + 1),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert response.status_code == 413


def test_zalo_webhook_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setenv("ZALO_WEBHOOK_SECRET", "zalo-secret-123")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/zalo/webhook",
                headers={"X-Bot-Api-Secret-Token": "wrong-secret"},
                json={"ok": True, "result": {"event_name": "message.text.received"}},
            )
            assert response.status_code == 403
    finally:
        get_settings.cache_clear()


def test_zalo_webhook_accepts_text_and_auto_replies(monkeypatch) -> None:
    sent_messages = []

    def fake_send_message(self, chat_id, text, parse_mode=None):
        sent_messages.append((chat_id, text, parse_mode))
        return True

    monkeypatch.setenv("ZALO_WEBHOOK_SECRET", "zalo-secret-123")
    monkeypatch.setenv("ZALO_BOT_TOKEN", "123456:test-token")
    get_settings.cache_clear()
    monkeypatch.setattr("app.presentation.routes.ZaloBotClient.send_message", fake_send_message)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/zalo/webhook",
                headers={"X-Bot-Api-Secret-Token": "zalo-secret-123"},
                json={
                    "ok": True,
                    "result": {
                        "event_name": "message.text.received",
                        "message": {
                            "chat": {"id": "chat-001", "chat_type": "PRIVATE"},
                            "text": "ping",
                        },
                    },
                },
            )
            assert response.status_code == 200
            assert response.json()["auto_replied"] is True
            assert sent_messages == [("chat-001", "pong", None)]
    finally:
        get_settings.cache_clear()


def test_zalo_webhook_understands_mentioned_ping(monkeypatch) -> None:
    sent_messages = []

    def fake_send_message(self, chat_id, text, parse_mode=None):
        sent_messages.append((chat_id, text, parse_mode))
        return True

    monkeypatch.setenv("ZALO_WEBHOOK_SECRET", "zalo-secret-123")
    monkeypatch.setenv("ZALO_BOT_TOKEN", "123456:test-token")
    get_settings.cache_clear()
    monkeypatch.setattr("app.presentation.routes.ZaloBotClient.send_message", fake_send_message)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/zalo/webhook",
                headers={"X-Bot-Api-Secret-Token": " zalo-secret-123 "},
                json={
                    "ok": True,
                    "result": {
                        "event_name": "message.text.received",
                        "message": {
                            "chat": {"id": "group-001", "chat_type": "GROUP"},
                            "text": "@Bot VNPT Can Tho ping",
                        },
                    },
                },
            )
            assert response.status_code == 200
            assert response.json()["auto_replied"] is True
            assert sent_messages == [("group-001", "pong", None)]
    finally:
        get_settings.cache_clear()


def test_zalo_webhook_accepts_result_json_string(monkeypatch) -> None:
    sent_messages = []

    def fake_send_message(self, chat_id, text, parse_mode=None):
        sent_messages.append((chat_id, text, parse_mode))
        return True

    monkeypatch.setenv("ZALO_WEBHOOK_SECRET", "zalo-secret-123")
    monkeypatch.setenv("ZALO_BOT_TOKEN", "123456:test-token")
    get_settings.cache_clear()
    monkeypatch.setattr("app.presentation.routes.ZaloBotClient.send_message", fake_send_message)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/zalo/webhook",
                headers={"X-Bot-Api-Secret-Token": "zalo-secret-123"},
                json={
                    "ok": True,
                    "result": json.dumps({
                        "event_name": "message.text.received",
                        "message": {
                            "from": {"id": "user-json-001", "display_name": "Json User"},
                            "chat": {"id": "chat-json-001", "chat_type": "PRIVATE"},
                            "text": "ping",
                            "message_id": "msg-json-001",
                        },
                    }),
                },
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["chat_id"] == "chat-json-001"
            assert payload["text"] == "ping"
            assert payload["message_id"] == "msg-json-001"
            assert sent_messages == [("chat-json-001", "pong", None)]
    finally:
        get_settings.cache_clear()


def test_admin_can_view_zalo_message_logs(monkeypatch) -> None:
    def fake_send_message(self, chat_id, text, parse_mode=None):
        return True

    monkeypatch.setenv("ZALO_WEBHOOK_SECRET", "zalo-secret-123")
    monkeypatch.setenv("ZALO_BOT_TOKEN", "123456:test-token")
    get_settings.cache_clear()
    monkeypatch.setattr("app.presentation.routes.ZaloBotClient.send_message", fake_send_message)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/zalo/webhook",
                headers={"X-Bot-Api-Secret-Token": "zalo-secret-123"},
                json={
                    "ok": True,
                    "result": {
                        "event_name": "message.text.received",
                        "message": {
                            "from": {"id": "user-log-001", "display_name": "Nguoi test log"},
                            "chat": {"id": "group-log-001", "chat_type": "GROUP"},
                            "message_id": "msg-log-001",
                            "text": "@Bot VNPT Can Tho ghi log",
                        },
                    },
                },
            )
            assert response.status_code == 200
            login(client)
            logs_response = client.get("/api/admin/zalo/message-logs?limit=20")
            assert logs_response.status_code == 200
            logs = logs_response.json()["logs"]
            assert any(log["direction"] == "in" and log["chat_id"] == "group-log-001" and "ghi log" in log["text"] for log in logs)
            assert any(log["direction"] == "out" and log["chat_id"] == "group-log-001" and log["ok"] is True for log in logs)
    finally:
        get_settings.cache_clear()


def test_admin_can_send_zalo_test_message_to_latest_chat(monkeypatch) -> None:
    sent_messages = []

    def fake_send_message(self, chat_id, text, parse_mode=None):
        sent_messages.append((chat_id, text, parse_mode))
        return True

    monkeypatch.setenv("ZALO_WEBHOOK_SECRET", "zalo-secret-123")
    monkeypatch.setenv("ZALO_BOT_TOKEN", "123456:test-token")
    get_settings.cache_clear()
    monkeypatch.setattr("app.presentation.routes.ZaloBotClient.send_message", fake_send_message)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/zalo/webhook",
                headers={"X-Bot-Api-Secret-Token": "zalo-secret-123"},
                json={
                    "ok": True,
                    "result": {
                        "event_name": "message.text.received",
                        "message": {
                            "from": {"id": "user-manual-001", "display_name": "Manual User"},
                            "chat": {"id": "chat-manual-001", "chat_type": "PRIVATE"},
                            "message_id": "msg-manual-001",
                            "text": "hello",
                        },
                    },
                },
            )
            assert response.status_code == 200
            login(client)
            response = client.post("/api/admin/zalo/send-test-message", json={})
            assert response.status_code == 200
            assert response.json()["chat_id"] == "chat-manual-001"
            assert sent_messages[-1] == ("chat-manual-001", "Tin nhan test tu Bot VNPT Can Tho.", None)
    finally:
        get_settings.cache_clear()


def test_admin_can_setup_zalo_webhook(monkeypatch) -> None:
    def fake_configure_webhook(self):
        return {"ok": True, "message": "Da cai dat webhook Zalo Bot.", "details": {"webhook_url": "https://vnptcto.com/api/zalo/webhook"}}

    monkeypatch.setattr("app.presentation.routes.ZaloBotClient.configure_webhook", fake_configure_webhook)
    with TestClient(app) as client:
        login(client)
        response = client.post("/api/admin/zalo/webhook/setup")
        assert response.status_code == 200
        assert response.json()["details"]["webhook_url"] == "https://vnptcto.com/api/zalo/webhook"


def test_system_connections_include_zalo_bot() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.get("/api/admin/connections")
        assert response.status_code == 200
        codes = {connection["code"] for connection in response.json()["connections"]}
        assert "zalo_bot" in codes


def test_admin_can_manage_report_links_and_active_links_are_public() -> None:
    with TestClient(app) as client:
        login(client)
        active_payload = {
            "ten_bao_cao": "Bao cao link active",
            "link": "https://docs.google.com/spreadsheets/d/sheet-link-active/edit#gid=0",
            "link_type": "google_sheet",
            "is_active": True,
        }
        created = client.post("/api/admin/report-links", json=active_payload)
        assert created.status_code == 200
        active_code = created.json()["ma_bao_cao"]
        assert active_code.startswith("LINK")

        inactive = client.post(
            "/api/admin/report-links",
            json={
                "ten_bao_cao": "Bao cao link inactive",
                "link": "https://drive.google.com/file/d/pdf-link-inactive/view",
                "link_type": "pdf",
                "is_active": False,
            },
        )
        assert inactive.status_code == 200

        form = client.post(
            "/api/admin/report-links",
            json={
                "ten_bao_cao": "Bieu mau Google",
                "link": "https://docs.google.com/forms/d/e/form-link/viewform",
                "link_type": "google_form",
                "is_active": True,
            },
        )
        assert form.status_code == 200

        duplicate_name = client.post(
            "/api/admin/report-links",
            json={**active_payload, "link": "https://docs.google.com/spreadsheets/d/another-sheet/edit"},
        )
        assert duplicate_name.status_code == 400
        assert "Ten bao cao" in duplicate_name.json()["detail"]

        duplicate_link = client.post(
            "/api/admin/report-links",
            json={**active_payload, "ten_bao_cao": "Bao cao link khac ten"},
        )
        assert duplicate_link.status_code == 400
        assert "Link nay" in duplicate_link.json()["detail"]

        admin_links = client.get("/api/report-links")
        assert admin_links.status_code == 200
        admin_payload = admin_links.json()["links"]
        active = next(item for item in admin_payload if item["ma_bao_cao"] == active_code)
        inactive_item = next(item for item in admin_payload if item["ten_bao_cao"] == "Bao cao link inactive")
        form_item = next(item for item in admin_payload if item["ten_bao_cao"] == "Bieu mau Google")
        assert active["download_url"].endswith(f"/api/report-links/{created.json()['id']}/download")
        assert inactive_item["is_active"] is False
        assert inactive_item["can_download"] is True
        assert form_item["can_download"] is False
        assert form_item["download_url"] == ""

        created_user = client.post(
            "/api/admin/users",
            json={
                "username": "viewer_report_links",
                "full_name": "Viewer Report Links",
                "role": "viewer",
                "password": "Viewer@Links2026!",
            },
        )
        assert created_user.status_code == 200
        client.post("/api/auth/logout")
        login(client, "viewer_report_links", "Viewer@Links2026!")

        navigation = client.get("/api/navigation")
        assert navigation.status_code == 200
        feature_codes = {feature["code"] for feature in navigation.json()["features"]}
        assert "baocaomoi" in feature_codes
        assert "linkbaocao" in feature_codes

        viewer_links = client.get("/api/report-links")
        assert viewer_links.status_code == 200
        viewer_names = {item["ten_bao_cao"] for item in viewer_links.json()["links"]}
        assert "Bao cao link active" in viewer_names
        assert "Bieu mau Google" in viewer_names
        assert "Bao cao link inactive" not in viewer_names


def test_internal_api_client_uses_active_connection_config() -> None:
    class FakeRepository:
        def get_system_connection_by_code(self, code: str) -> dict:
            assert code == "internal_fastapi_api"
            return {
                "connection_type": "internal_api",
                "is_active": True,
                "config": {
                    "url": "https://current-internal-api.example/api/du-lieu-web",
                    "mock_mode": "true",
                    "token": "connection-token",
                },
            }

    settings = Settings(
        internal_api_url="https://old-env-url.example/api/du-lieu-web",
        internal_api_mock_mode=False,
        internal_api_token="env-token",
    )

    client = routes.InternalApiClient.from_repository(settings, FakeRepository())

    assert client.api_url == "https://current-internal-api.example/api/du-lieu-web"
    assert client.mock_mode is True
    assert client.token == "connection-token"
    assert client.health_check()["api_url"] == "https://current-internal-api.example/api/du-lieu-web"


def test_internal_api_dns_error_message_points_to_tunnel_config() -> None:
    message = DatabaseService._internal_api_connection_message(Exception("[Errno 11001] getaddrinfo failed"))

    assert "Không phân giải được tên miền API dữ liệu nội bộ" in message
    assert "URL tunnel" in message


def test_seed_current_connections_preserves_internal_api_admin_config(tmp_path) -> None:
    repository = routes.AppRepository(str(tmp_path / "app.db"))
    repository.initialize("admin", "Admin@Brcd2026!")
    repository.upsert_system_connection(
        "internal_fastapi_api",
        "API du lieu noi bo",
        "internal_api",
        "Custom internal API",
        {
            "url": "https://current-internal-api.example/api/du-lieu-web",
            "mock_mode": False,
            "secret_ref": "INTERNAL_API_TOKEN",
        },
        True,
    )

    routes.ConnectionService(
        repository,
        Settings(
            internal_api_url="https://old-env-url.example/api/du-lieu-web",
            internal_api_mock_mode=True,
        ),
    ).seed_current_connections()

    stored = repository.get_system_connection_by_code("internal_fastapi_api")
    assert stored["config"]["url"] == "https://current-internal-api.example/api/du-lieu-web"
    assert stored["config"]["mock_mode"] is False


def test_admin_can_manage_zalo_auto_messages_and_captures(monkeypatch) -> None:
    monkeypatch.setenv("APP_PUBLIC_URL", "https://vnptcto.com")
    get_settings.cache_clear()
    tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    try:
        with TestClient(app) as client:
            login(client)
            created = client.post(
                "/api/admin/zalo/auto-messages",
                json={
                    "name": "Dashboard 7h",
                    "page_url": "/dashboard",
                    "page_label": "Dashboard kinh doanh",
                    "schedule_type": "Daily",
                    "run_time": "07:00",
                    "target_type": "group",
                    "chat_id": "group-auto-001",
                    "caption": "Anh chup dashboard",
                    "is_active": True,
                },
            )
            assert created.status_code == 200
            schedule = created.json()["schedule"]
            assert schedule["schedule_id"].startswith("ZALO")

            listed = client.get("/api/admin/zalo/auto-messages")
            assert listed.status_code == 200
            assert any(item["schedule_id"] == schedule["schedule_id"] for item in listed.json()["schedules"])

            uploaded = client.post(
                f"/api/admin/zalo/auto-messages/{schedule['schedule_id']}/captures",
                json={"image_base64": f"data:image/png;base64,{tiny_png}", "mime_type": "image/png", "page_url": "/dashboard"},
            )
            assert uploaded.status_code == 200
            capture = uploaded.json()["capture"]
            assert uploaded.json()["capture_url"].startswith("https://vnptcto.com/api/zalo/auto-message-captures/")

            denied = client.get(f"/api/zalo/auto-message-captures/{capture['capture_id']}?token=wrong")
            assert denied.status_code == 404
            image = client.get(f"/api/zalo/auto-message-captures/{capture['capture_id']}?token={capture['public_token']}")
            assert image.status_code == 200
            assert image.headers["content-type"].startswith("image/png")
            assert image.content.startswith(b"\x89PNG")
    finally:
        get_settings.cache_clear()


def test_active_zalo_auto_message_requires_one_target() -> None:
    with TestClient(app) as client:
        login(client)
        no_target = client.post(
            "/api/admin/zalo/auto-messages",
            json={
                "name": "Bao cao chua chon dich",
                "page_url": "/dashboard",
                "schedule_type": "Daily",
                "run_time": "07:00",
                "target_type": "group",
                "chat_id": "",
                "is_active": True,
            },
        )
        assert no_target.status_code == 400
        assert "Chua chon" in no_target.json()["detail"]

        many_targets = client.post(
            "/api/admin/zalo/auto-messages",
            json={
                "name": "Bao cao nhieu dich",
                "page_url": "/dashboard",
                "schedule_type": "Daily",
                "run_time": "07:00",
                "target_type": "person",
                "chat_id": "chat-a,chat-b",
                "is_active": True,
            },
        )
        assert many_targets.status_code == 400
        assert "1 chat_id" in many_targets.json()["detail"]

        disabled_draft = client.post(
            "/api/admin/zalo/auto-messages",
            json={
                "name": "Ban nhap Zalo",
                "page_url": "/dashboard",
                "schedule_type": "Daily",
                "run_time": "07:00",
                "target_type": "group",
                "chat_id": "",
                "is_active": False,
            },
        )
        assert disabled_draft.status_code == 200
        assert disabled_draft.json()["schedule"]["is_active"] is False


def test_zalo_auto_capture_session_cookie_opens_authenticated_page() -> None:
    from app.application.zalo_auto_message_service import signed_capture_session_cookie

    with TestClient(app) as client:
        repository = routes.build_app_repository()
        user = repository.get_user_by_username(get_settings().initial_admin_username)
        assert user is not None
        client.cookies.set("brcd_session", signed_capture_session_cookie(get_settings(), user))

        response = client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["user"]["username"] == user["username"]


def test_zalo_auto_capture_playwright_cookie_uses_url_only(monkeypatch) -> None:
    from app.application.zalo_auto_message_service import playwright_session_cookie

    monkeypatch.setenv("APP_PUBLIC_URL", "https://vnptcto.com")
    get_settings.cache_clear()
    try:
        with TestClient(app):
            repository = routes.build_app_repository()
            user = repository.get_user_by_username(get_settings().initial_admin_username)
            assert user is not None

            cookie = playwright_session_cookie(get_settings(), user)
            assert cookie["url"] == "https://vnptcto.com"
            assert "path" not in cookie
            assert cookie["secure"] is True
    finally:
        get_settings.cache_clear()


def test_zalo_auto_capture_uses_dashboard_area(monkeypatch) -> None:
    from app.application import zalo_auto_message_service as service

    calls = {}

    class FakeRepository:
        def save_zalo_message_capture(self, schedule_id, image_base64, mime_type, page_url="", created_by=""):
            calls["saved"] = {
                "schedule_id": schedule_id,
                "image_base64": image_base64,
                "mime_type": mime_type,
                "page_url": page_url,
                "created_by": created_by,
            }
            return {"capture_id": "CAPTEST", "public_token": "token"}

    def fake_capture_page_screenshot_bytes(repository, settings, page_url, selector=service.DASHBOARD_CAPTURE_SELECTOR):
        calls["capture"] = {"page_url": page_url, "selector": selector}
        return b"\x89PNG\r\n"

    monkeypatch.setenv("APP_PUBLIC_URL", "https://vnptcto.com")
    get_settings.cache_clear()
    monkeypatch.setattr(service, "capture_page_screenshot_bytes", fake_capture_page_screenshot_bytes)
    try:
        result = service.capture_schedule_page_image(
            FakeRepository(),
            get_settings(),
            {"schedule_id": "ZALO0001", "page_url": "/dashboardtest"},
        )
        assert result["ok"] is True
        assert calls["capture"] == {"page_url": "/dashboardtest", "selector": service.DASHBOARD_CAPTURE_SELECTOR}
        assert calls["saved"]["image_base64"] == "iVBORw0K"
        assert result["capture_url"] == "https://vnptcto.com/api/zalo/auto-message-captures/CAPTEST?token=token"
    finally:
        get_settings.cache_clear()


def test_zalo_auto_message_scheduler_sends_due_photo(monkeypatch) -> None:
    from app.application.task_scheduler import LOCAL_TIMEZONE, ZaloAutoMessageScheduler

    events = []
    sent_messages = []

    def fake_send_photo(self, chat_id, photo_url, caption=""):
        events.append(("send", photo_url))
        sent_messages.append((chat_id, photo_url, caption))
        return True

    def fake_refresh_schedule_data(repository, settings, schedule):
        events.append(("refresh", schedule.get("page_url")))
        return {"ok": True, "page_id": "DASHBOARD_KINH_DOANH"}

    def fake_capture_schedule_page_image(repository, settings, schedule):
        events.append(("capture", schedule.get("page_url")))
        return {
            "ok": True,
            "capture": {"capture_id": "CAPTEST", "public_token": "token"},
            "capture_url": "https://vnptcto.com/api/zalo/auto-message-captures/CAPTEST?token=token",
        }

    monkeypatch.setenv("ZALO_BOT_TOKEN", "123456:test-token")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.zalo_auto_message_service.ZaloBotClient.send_photo", fake_send_photo)
    monkeypatch.setattr("app.application.zalo_auto_message_service.refresh_schedule_data", fake_refresh_schedule_data)
    monkeypatch.setattr("app.application.zalo_auto_message_service.capture_schedule_page_image", fake_capture_schedule_page_image)
    try:
        with TestClient(app) as client:
            login(client)
            created = client.post(
                "/api/admin/zalo/auto-messages",
                json={
                    "name": "Bao cao sang",
                    "page_url": "/dashboard",
                    "schedule_type": "Daily",
                    "run_time": "07:05",
                    "target_type": "person",
                    "chat_id": "chat-auto-001",
                    "caption": "Bao cao sang",
                    "photo_url": "https://example.com/dashboard.png",
                    "is_active": True,
                },
            )
            assert created.status_code == 200

            scheduler = ZaloAutoMessageScheduler()
            scheduler.configure(routes.build_app_repository(), get_settings())
            now = datetime(2026, 1, 5, 7, 5, tzinfo=LOCAL_TIMEZONE)
            assert scheduler.check_due_messages(now) == 1
            assert [event[0] for event in events] == ["refresh", "capture", "send"]
            assert sent_messages[-1] == (
                "chat-auto-001",
                "https://vnptcto.com/api/zalo/auto-message-captures/CAPTEST?token=token",
                "Bao cao sang",
            )
            assert scheduler.check_due_messages(now) == 0
    finally:
        get_settings.cache_clear()


def test_zalo_auto_message_requires_explicit_chat_id(monkeypatch) -> None:
    from app.application import zalo_auto_message_service as service

    refresh_calls = []

    class FakeRepository:
        def list_audit_logs(self, limit=500):
            return [{"action": "zalo_message_received", "details": '{"chat_id":"latest-chat"}'}]

    def fake_refresh_schedule_data(repository, settings, schedule):
        refresh_calls.append(schedule)
        return {"ok": True}

    monkeypatch.setattr(service, "refresh_schedule_data", fake_refresh_schedule_data)
    result = service.send_zalo_auto_message(
        FakeRepository(),
        get_settings(),
        {"schedule_id": "ZALOEMPTY", "name": "Bao cao", "chat_id": "", "page_url": "/dashboard"},
    )

    assert result["ok"] is False
    assert result["chat_id"] == ""
    assert "chat_id" in result["message"]
    assert refresh_calls == []


def test_admin_can_manage_data_mining_schedules_and_run_now(monkeypatch) -> None:
    calls = []

    def fake_run_data_mining_schedule(repository, settings, schedule, **kwargs):
        calls.append({
            "schedule_id": schedule["schedule_id"],
            "otp": kwargs.get("otp"),
            "created_by": kwargs.get("created_by"),
            "parameter_overrides": kwargs.get("parameter_overrides"),
        })
        run = kwargs.get("existing_run") or repository.create_data_mining_run(
            schedule["schedule_id"],
            schedule.get("parameters"),
            created_by=kwargs.get("created_by") or "",
        )
        result = {
            "ok": True,
            "status": "success",
            "message": "Da tai bao cao OneBSS.",
            "file_name": "bien_dong_0700_08072026.xlsx",
            "file_path": "data/data_mining_downloads/bien_dong_0700_08072026.xlsx",
            "storage_status": "saved_local",
        }
        repository.finish_data_mining_run(run["run_id"], result)
        return {**result, "run_id": run["run_id"], "schedule_id": schedule["schedule_id"]}

    monkeypatch.setattr(routes, "run_data_mining_schedule", fake_run_data_mining_schedule)
    with TestClient(app) as client:
        login(client)
        report_url = "https://onebss.vnpt.vn/#/report/bi?path=PHATTRIENTHUEBAO%2FBIENDONGPHATTRIENTHUEBAO%2FRP_BSS_28429&name=Test"
        created = client.post(
            "/api/admin/data-mining/schedules",
            json={
                "name": "Bien dong thue bao",
                "report_url": report_url,
                "schedule_type": "Daily",
                "run_time": "07:00",
                "storage_link": "data/test_downloads",
                "file_name_template": "bien_dong",
                "parameters": {"P_TUNGAY": "01/07/2026", "P_DENNGAY": "08/07/2026"},
                "is_active": True,
            },
        )
        assert created.status_code == 200
        schedule = created.json()["schedule"]
        assert schedule["schedule_id"].startswith("MINE")
        assert schedule["parameters"]["P_TUNGAY"] == "01/07/2026"

        listed = client.get("/api/admin/data-mining/schedules")
        assert listed.status_code == 200
        assert any(item["schedule_id"] == schedule["schedule_id"] for item in listed.json()["schedules"])

        run_now = client.post(
            f"/api/admin/data-mining/schedules/{schedule['schedule_id']}/run-now",
            json={"otp": "123456", "allow_device_registration": True, "parameters": {"P_DENNGAY": "09/07/2026"}},
        )
        assert run_now.status_code == 200
        assert run_now.json()["ok"] is True
        assert run_now.json()["status"] == "queued"
        for _ in range(20):
            if calls:
                break
            time.sleep(0.05)
        assert calls[-1]["otp"] == "123456"
        assert calls[-1]["parameter_overrides"] == {"P_DENNGAY": "09/07/2026"}

        runs = []
        for _ in range(20):
            runs = client.get(f"/api/admin/data-mining/runs?schedule_id={schedule['schedule_id']}").json()["runs"]
            if runs and runs[0]["status"] == "success":
                break
            time.sleep(0.05)
        assert len(runs) == 1
        assert runs[0]["file_name"] == "bien_dong_0700_08072026.xlsx"

        assert client.delete(f"/api/admin/data-mining/schedules/{schedule['schedule_id']}").status_code == 200
        assert client.get(f"/api/admin/data-mining/runs?schedule_id={schedule['schedule_id']}").json()["runs"] == []


def test_google_drive_folder_link_and_storage_upload(monkeypatch, tmp_path) -> None:
    from app.application import onebss_data_mining_service as service
    from app.application.google_drive_service import extract_google_drive_folder_id

    uploaded_calls = []

    def fake_upload_file_to_google_drive(settings, local_path, file_name, folder_id):
        uploaded_calls.append((str(local_path), file_name, folder_id))
        return {"file_id": "drive-file-001", "web_view_link": "https://drive.google.com/file/d/drive-file-001/view"}

    local_file = tmp_path / "report.xlsx"
    local_file.write_bytes(b"excel")
    monkeypatch.setattr(service, "upload_file_to_google_drive", fake_upload_file_to_google_drive)

    folder_url = "https://drive.google.com/drive/folders/1TJqLjq8OpZ_x_D-djxRk0w4HacUh4HmS"
    assert extract_google_drive_folder_id(folder_url) == "1TJqLjq8OpZ_x_D-djxRk0w4HacUh4HmS"
    result = service.save_downloaded_file(get_settings(), local_file, folder_url)
    assert result["ok"] is True
    assert result["storage_link"] == "https://drive.google.com/file/d/drive-file-001/view"
    assert result["storage_status"] == "uploaded_google_drive:drive-file-001"
    assert uploaded_calls == [(str(local_file), "report.xlsx", "1TJqLjq8OpZ_x_D-djxRk0w4HacUh4HmS")]


def test_google_drive_oauth_start_and_protected_config(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_DRIVE_OAUTH_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://vnptcto.com")
    get_settings.cache_clear()
    with TestClient(app) as client:
        login(client)
        repository = routes.build_app_repository()
        repository.upsert_system_connection(
            "drive_storage",
            "Google Drive",
            "drive",
            "Drive OAuth",
            {
                "provider": "google_drive_oauth",
                "folder": "folder-001",
                "oauth_email": "owner@example.com",
                "oauth_refresh_token_enc": "enc:stored-refresh-token",
            },
            True,
        )

        connections = client.get("/api/admin/connections")
        assert connections.status_code == 200
        drive = next(item for item in connections.json()["connections"] if item["code"] == "drive_storage")
        assert "oauth_refresh_token_enc" not in drive["config"]
        assert "oauth_refresh_token_enc" in drive["protected_config_keys"]

        saved = client.put(
            "/api/admin/connections/drive_storage",
            json={
                "name": "Google Drive",
                "connection_type": "drive",
                "description": "Drive OAuth",
                "config": {"provider": "google_drive_oauth", "folder": "folder-002"},
                "is_active": True,
            },
        )
        assert saved.status_code == 200
        stored = repository.get_system_connection_by_code("drive_storage")
        assert stored["config"]["folder"] == "folder-002"
        assert stored["config"]["oauth_refresh_token_enc"] == "enc:stored-refresh-token"

        start = client.post("/api/google-drive/oauth/start")
        assert start.status_code == 200
        body = start.json()
        assert body["redirect_uri"] == "https://vnptcto.com/api/google-drive/oauth/callback"
        assert "https://accounts.google.com/o/oauth2/v2/auth" in body["authorization_url"]
        assert "access_type=offline" in body["authorization_url"]
    monkeypatch.delenv("GOOGLE_DRIVE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("APP_PUBLIC_URL", raising=False)
    get_settings.cache_clear()


def test_data_mining_dynamic_date_parameters() -> None:
    from app.application.onebss_data_mining_service import LOCAL_TIMEZONE, resolve_dynamic_parameters

    now = datetime(2026, 7, 8, 9, 30, tzinfo=LOCAL_TIMEZONE)
    params = resolve_dynamic_parameters(
        {
            "P_TUNGAY": "{{month_start}}",
            "P_DENNGAY": "{{today}}",
            "P_HOMQUA": "{{yesterday}}",
            "P_CUOITHANG": "{{month_end}}",
            "P_OFFSET": "{{today-7d}}",
            "P_STATIC": "13",
        },
        now,
    )
    assert params["P_TUNGAY"] == "01/07/2026"
    assert params["P_DENNGAY"] == "08/07/2026"
    assert params["P_HOMQUA"] == "07/07/2026"
    assert params["P_CUOITHANG"] == "31/07/2026"
    assert params["P_OFFSET"] == "01/07/2026"
    assert params["P_STATIC"] == "13"


def test_data_mining_run_resolves_parameters_before_download(monkeypatch) -> None:
    from app.application import onebss_data_mining_service as service

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 8, 9, 30, tzinfo=tz)

    class FakeRepository:
        def __init__(self):
            self.created_parameters = None
            self.finished_result = None

        def create_data_mining_run(self, schedule_id, parameters, created_by=""):
            self.created_parameters = parameters
            return {"run_id": "RUN001", "schedule_id": schedule_id, "parameters": parameters}

        def finish_data_mining_run(self, run_id, result):
            self.finished_result = result

    class FakeDownloader:
        def __init__(self, settings):
            self.settings = settings

        def download_report(self, schedule, **kwargs):
            return {
                "ok": True,
                "status": "success",
                "message": "ok",
                "parameters": schedule["parameters"],
            }

    monkeypatch.setattr(service, "datetime", FixedDateTime)
    monkeypatch.setattr(service, "OneBssReportDownloader", FakeDownloader)
    repository = FakeRepository()
    result = service.run_data_mining_schedule(
        repository,
        get_settings(),
        {
            "schedule_id": "MINE0001",
            "parameters": {"P_TUNGAY": "{{month_start}}", "P_DENNGAY": "{{today}}"},
        },
        parameter_overrides={"P_DENNGAY": "{{today-1d}}"},
        created_by="admin",
    )
    assert repository.created_parameters == {"P_TUNGAY": "01/07/2026", "P_DENNGAY": "07/07/2026"}
    assert result["parameters"] == repository.created_parameters


def test_data_mining_scheduler_runs_due_schedule_once(monkeypatch) -> None:
    from app.application.task_scheduler import DataMiningScheduler, LOCAL_TIMEZONE

    calls = []

    def fake_run_data_mining_schedule(repository, settings, schedule, **kwargs):
        calls.append((schedule["schedule_id"], kwargs.get("interactive")))
        return {
            "ok": True,
            "status": "success",
            "message": "Da tai bao cao OneBSS.",
            "file_name": "scheduler_0711_08072026.xlsx",
            "file_path": "data/data_mining_downloads/scheduler_0711_08072026.xlsx",
        }

    monkeypatch.setattr("app.application.task_scheduler.run_data_mining_schedule", fake_run_data_mining_schedule)
    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/data-mining/schedules",
            json={
                "name": "Scheduler OneBSS",
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=PHATTRIENTHUEBAO%2FBIENDONGPHATTRIENTHUEBAO%2FRP_BSS_28429&name=Test",
                "schedule_type": "Daily",
                "run_time": "07:11",
                "file_name_template": "scheduler",
                "parameters": {},
                "is_active": True,
            },
        )
        assert created.status_code == 200
        schedule_id = created.json()["schedule"]["schedule_id"]

        scheduler = DataMiningScheduler()
        scheduler.configure(routes.build_app_repository(), get_settings())
        now = datetime(2026, 7, 8, 7, 11, tzinfo=LOCAL_TIMEZONE)
        assert scheduler.check_due_schedules(now) == 1
        assert calls == [(schedule_id, False)]
        assert scheduler.check_due_schedules(now) == 0

        refreshed = routes.build_app_repository().get_data_mining_schedule(schedule_id)
        assert refreshed["last_status"] == "success"
        assert refreshed["last_file_name"] == "scheduler_0711_08072026.xlsx"


def test_admin_can_manage_work_tasks() -> None:
    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_cong_viec": "Gia cuoc",
            "type": "Daily",
            "time": "07:00",
            "weekday": "",
            "once_date": "",
            "group": "ME",
            "check": False,
        }
        created = client.post("/api/admin/work-tasks", json=payload)
        assert created.status_code == 200
        task_id = created.json()["task"]["task_id"]
        assert task_id.startswith("TASK")

        tasks = client.get("/api/admin/work-tasks").json()["tasks"]
        assert any(task["task_id"] == task_id and task["check"] is False for task in tasks)

        completed = client.post(f"/api/admin/work-tasks/{task_id}/complete")
        assert completed.status_code == 200
        active_tasks = client.get("/api/admin/work-tasks").json()["tasks"]
        assert all(task["task_id"] != task_id for task in active_tasks)

        all_tasks = client.get("/api/admin/work-tasks?include_completed=true").json()["tasks"]
        assert any(task["task_id"] == task_id and task["check"] is True for task in all_tasks)


def test_database_health_requires_login_and_uses_mock_mode() -> None:
    with TestClient(app) as client:
        assert client.get("/api/health/database").status_code == 401
        login(client)
        response = client.get("/api/health/database")
        assert response.status_code == 200
        assert response.json()["details"]["mode"] == "mock"


def test_dashboard_datcoc_table_uses_internal_api() -> None:
    with TestClient(app) as client:
        assert client.get("/api/dashboard/datcoc-test").status_code == 401
        login(client)
        response = client.get("/api/dashboard/datcoc-test")
        assert response.status_code == 200
        payload = response.json()
        assert payload["sql"] == "select * from css_cto.db_datcoc where ma_tb = 'thanhbinh-omon'"
        assert payload["columns"]
        assert payload["rows"]


def test_dashboard_fiber_uses_internal_api() -> None:
    with TestClient(app) as client:
        assert client.get("/api/dashboard/fiber").status_code == 401
        login(client)
        response = client.get("/api/dashboard/fiber")
        assert response.status_code == 200
        payload = response.json()
        assert payload["groups"]["vnpt"]["rows"][0]["rank"] == 1
        assert len(payload["groups"]["vnpt"]["rows"]) == 13
        assert len(payload["groups"]["ttvt"]["rows"]) == 13
        assert payload["summary"]["production"]["fiber"] == payload["groups"]["vnpt"]["total"]


def test_system_status_requires_login_and_reports_internal_api_policy() -> None:
    with TestClient(app) as client:
        assert client.get("/api/system/status").status_code == 401
        login(client)
        response = client.get("/api/system/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["internal_api"]["mock_mode"] is True
        assert payload["internal_api"]["url"] == "http://10.92.17.88:8000/api/du-lieu-web"
        assert payload["query_policy"]["data_source"] == "internal_fastapi"
        assert payload["query_policy"]["page_size_max"] == 50


def test_admin_can_manage_sql_reports_and_run_dynamic_report() -> None:
    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_bao_cao": "Báo cáo thuê bao test",
            "ma_bao_cao": "BC_TEST_THUE_BAO",
            "cau_lenh_sql": "SELECT ma_tb, ten_tb FROM css_cto.db_thuebao WHERE trang_thai = :status;",
            "cac_tham_so": ["status"],
        }
        created = client.post("/api/admin/sql-reports", json=payload)
        assert created.status_code == 200

        reports = client.get("/api/admin/sql-reports")
        assert reports.status_code == 200
        assert any(report["ma_bao_cao"] == "BC_TEST_THUE_BAO" for report in reports.json()["reports"])

        public_configs = client.get("/api/reports/configs")
        assert public_configs.status_code == 200
        first_config = next(report for report in public_configs.json()["reports"] if report["ma_bao_cao"] == "BC_TEST_THUE_BAO")
        assert "cau_lenh_sql" not in first_config

        result = client.post(
            "/api/reports/run",
            json={"ma_bao_cao": "BC_TEST_THUE_BAO", "filters": {"status": "1"}, "page": 1, "page_size": 20},
        )
        assert result.status_code == 200
        body = result.json()
        assert body["columns"] == ["STT", "MA_BAO_CAO", "TEN_BAO_CAO", "THAM_SO"]
        assert body["pagination"]["page_size"] == 20


def test_dynamic_report_history_records_loaded_result(monkeypatch) -> None:
    def fake_run_sql_report(self, **kwargs):
        return {
            "ok": True,
            "columns": ["MA_TB", "TEN_TB"],
            "rows": [{"MA_TB": "tb-history", "TEN_TB": "Thue bao history"}],
            "total": 1,
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
            "message": "ok",
        }

    monkeypatch.setattr(routes.InternalApiClient, "run_sql_report", fake_run_sql_report)

    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_bao_cao": "Bao cao lich su",
            "ma_bao_cao": "BC_HISTORY_LOAD",
            "cau_lenh_sql": "SELECT ma_tb, ten_tb FROM css_cto.db_thuebao;",
            "cac_tham_so": [],
        }
        assert client.post("/api/admin/sql-reports", json=payload).status_code == 200
        result = client.post(
            "/api/reports/run",
            json={"ma_bao_cao": "BC_HISTORY_LOAD", "filters": {}, "page": 1, "page_size": 20},
        )
        assert result.status_code == 200

        history = client.get("/api/reports/history?limit=20")
        assert history.status_code == 200
        items = history.json()["items"]
        item = next(row for row in items if row["ma_bao_cao"] == "BC_HISTORY_LOAD")
        assert item["event_type"] == "load"
        assert item["status"] == "success"
        assert item["rows"] == 1
        assert item["total"] == 1


def test_dynamic_report_search_and_excel_export_use_full_result_set(monkeypatch) -> None:
    rows = [
        {"MA_TB": "tb001", "TEN_TB": "Nguyen Van A", "DIACHI_LD": "Can Tho"},
        {"MA_TB": "tb002", "TEN_TB": "Tran Binh", "DIACHI_LD": "Soc Trang"},
        {"MA_TB": "tb003", "TEN_TB": "Phan Thuy Ngan", "DIACHI_LD": "Can Tho"},
    ]
    calls = []

    def fake_run_sql_report(self, **kwargs):
        calls.append(kwargs)
        result_rows = rows
        search_value = str(kwargs.get("tham_so", {}).get("SEARCH_TERM_1", "")).strip("%").lower()
        if search_value:
            result_rows = [
                row for row in rows
                if search_value in " ".join(str(value).lower() for value in row.values())
            ]
        return {
            "ok": True,
            "columns": ["MA_TB", "TEN_TB", "DIACHI_LD"],
            "rows": result_rows,
            "total": len(result_rows),
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
            "message": "ok",
        }

    monkeypatch.setattr(routes.InternalApiClient, "run_sql_report", fake_run_sql_report)

    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_bao_cao": "Bao cao search export",
            "ma_bao_cao": "BC_SEARCH_EXPORT",
            "cau_lenh_sql": "SELECT ma_tb, ten_tb, diachi_ld FROM css_cto.db_thuebao;",
            "cac_tham_so": [],
        }
        assert client.post("/api/admin/sql-reports", json=payload).status_code == 200

        result = client.post(
            "/api/reports/run",
            json={
                "ma_bao_cao": "BC_SEARCH_EXPORT",
                "filters": {},
                "search": "phan thuy",
                "search_columns": ["MA_TB", "TEN_TB", "DIACHI_LD"],
                "page": 1,
                "page_size": 20,
            },
        )
        assert result.status_code == 200
        body = result.json()
        assert body["pagination"]["total"] == 1
        assert body["rows"][0]["MA_TB"] == "tb003"
        assert calls[-1]["page_size"] == 20
        assert "WHERE" in calls[-1]["cau_lenh_sql"]

        export = client.post(
            "/api/reports/export",
            json={
                "ma_bao_cao": "BC_SEARCH_EXPORT",
                "filters": {},
                "search": "can tho",
                "search_columns": ["MA_TB", "TEN_TB", "DIACHI_LD"],
                "page": 1,
                "page_size": 20,
            },
        )
        assert export.status_code == 200
        assert export.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        workbook = openpyxl.load_workbook(BytesIO(export.content))
        sheet = workbook.active
        assert [cell.value for cell in sheet[1]] == ["MA_TB", "TEN_TB", "DIACHI_LD"]
        assert sheet.max_row == 3
        assert {sheet.cell(row=index, column=1).value for index in range(2, sheet.max_row + 1)} == {"tb001", "tb003"}

        loaded_export = client.post(
            "/api/reports/export-loaded",
            json={
                "ma_bao_cao": "BC_SEARCH_EXPORT",
                "columns": ["MA_TB", "TEN_TB", "DIACHI_LD"],
                "rows": [rows[2]],
                "search": "phan thuy",
            },
        )
        assert loaded_export.status_code == 200
        loaded_workbook = openpyxl.load_workbook(BytesIO(loaded_export.content))
        loaded_sheet = loaded_workbook.active
        assert loaded_sheet.max_row == 2
        assert loaded_sheet["A2"].value == "tb003"


def test_dynamic_report_export_job_downloads_full_result_set(monkeypatch) -> None:
    rows = [
        {"MA_TB": f"tb{index:04d}", "TEN_TB": f"Thue bao {index:04d}"}
        for index in range(5205)
    ]
    calls = []

    def fake_run_sql_report(self, **kwargs):
        calls.append(kwargs)
        page = int(kwargs["page"])
        page_size = int(kwargs["page_size"])
        start = (page - 1) * page_size
        return {
            "ok": True,
            "columns": ["MA_TB", "TEN_TB"],
            "rows": rows[start:start + page_size],
            "total": len(rows),
            "page": page,
            "page_size": page_size,
            "message": "ok",
        }

    monkeypatch.setattr(routes.InternalApiClient, "run_sql_report", fake_run_sql_report)

    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_bao_cao": "Bao cao export job",
            "ma_bao_cao": "BC_EXPORT_JOB",
            "cau_lenh_sql": "SELECT ma_tb, ten_tb FROM css_cto.db_thuebao;",
            "cac_tham_so": [],
        }
        assert client.post("/api/admin/sql-reports", json=payload).status_code == 200

        started = client.post(
            "/api/reports/export-jobs",
            json={"ma_bao_cao": "BC_EXPORT_JOB", "filters": {}, "page": 1, "page_size": 20},
        )
        assert started.status_code == 200
        job_id = started.json()["job_id"]

        status_body = {}
        for _ in range(80):
            status_response = client.get(f"/api/reports/export-jobs/{job_id}")
            assert status_response.status_code == 200
            status_body = status_response.json()
            if status_body["status"] == "complete":
                break
            time.sleep(0.05)

        assert status_body["status"] == "complete"
        assert status_body["rows"] == len(rows)
        assert [call["page"] for call in calls] == [1, 2]
        assert all(call["page_size"] == 5000 for call in calls)
        assert all(call.get("timeout", 0) >= 20 for call in calls)

        download = client.get(status_body["download_url"])
        assert download.status_code == 200
        workbook = openpyxl.load_workbook(BytesIO(download.content), read_only=True)
        sheet = workbook.active
        exported_rows = list(sheet.iter_rows(values_only=True))
        assert len(exported_rows) == len(rows) + 1
        assert list(exported_rows[0]) == ["MA_TB", "TEN_TB"]
        assert exported_rows[-1][0] == "tb5204"


def test_dynamic_report_export_queue_can_cancel_waiting_job(monkeypatch) -> None:
    started_first = threading.Event()
    release_first = threading.Event()
    calls = []

    def fake_export_dynamic_report(self, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            started_first.set()
            release_first.wait(2)
        return {
            "ok": True,
            "report": {"ma_bao_cao": kwargs["ma_bao_cao"], "ten_bao_cao": kwargs["ma_bao_cao"]},
            "columns": ["MA_TB"],
            "rows": [],
            "details": {"export_rows": 1, "fetched_total": 1},
        }

    monkeypatch.setattr(routes, "google_drive_folder_id", lambda settings, storage_link="": "")
    monkeypatch.setattr(DatabaseService, "export_dynamic_report", fake_export_dynamic_report)

    with routes.DYNAMIC_REPORT_EXPORT_JOBS_LOCK:
        routes.DYNAMIC_REPORT_EXPORT_JOBS.clear()

    try:
        with TestClient(app) as client:
            login(client)
            first = client.post("/api/reports/export-jobs", json={"ma_bao_cao": "QUEUE_A", "filters": {}, "page": 1, "page_size": 20})
            assert first.status_code == 200
            assert started_first.wait(1)

            second = client.post("/api/reports/export-jobs", json={"ma_bao_cao": "QUEUE_B", "filters": {}, "page": 1, "page_size": 20})
            assert second.status_code == 200
            second_job_id = second.json()["job_id"]

            queue = client.get("/api/reports/export-jobs?limit=10")
            assert queue.status_code == 200
            queued_job = next(job for job in queue.json()["jobs"] if job["job_id"] == second_job_id)
            assert queued_job["status"] == "queued"
            assert queued_job["queue_position"] >= 1
            assert queued_job["can_cancel"] is True

            cancelled = client.delete(f"/api/reports/export-jobs/{second_job_id}")
            assert cancelled.status_code == 200
            cancelled_body = cancelled.json()
            assert cancelled_body["status"] == "cancelled"
            assert cancelled_body["can_cancel"] is False
    finally:
        release_first.set()


def test_dynamic_report_export_job_can_return_drive_link(monkeypatch) -> None:
    calls = []

    def fake_drive_folder_id(settings, storage_link=""):
        return "drive-folder-001"

    def fake_export_to_drive(self, **kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "drive_url": "https://drive.google.com/file/d/export-file/view",
            "file_name": "crs_export.xlsx",
            "rows": 145433,
            "total": 145433,
        }

    monkeypatch.setattr(routes, "google_drive_folder_id", fake_drive_folder_id)
    monkeypatch.setattr(DatabaseService, "export_dynamic_report_to_drive", fake_export_to_drive)

    with TestClient(app) as client:
        login(client)
        started = client.post(
            "/api/reports/export-jobs",
            json={"ma_bao_cao": "CRS", "filters": {}, "page": 1, "page_size": 20},
        )
        assert started.status_code == 200
        job_id = started.json()["job_id"]

        status_body = {}
        for _ in range(80):
            status_response = client.get(f"/api/reports/export-jobs/{job_id}")
            assert status_response.status_code == 200
            status_body = status_response.json()
            if status_body["status"] == "complete":
                break
            time.sleep(0.05)

        assert status_body["status"] == "complete"
        assert status_body["drive_url"] == "https://drive.google.com/file/d/export-file/view"
        assert status_body["download_url"] == status_body["drive_url"]
        assert status_body["rows"] == 145433
        assert calls[0]["drive_folder_id"] == "drive-folder-001"
        assert calls[0]["ma_bao_cao"] == "CRS"


def test_dynamic_report_export_job_status_recovers_from_persisted_metadata(monkeypatch, tmp_path) -> None:
    def fake_drive_folder_id(settings, storage_link=""):
        return "drive-folder-001"

    def fake_export_to_drive(self, **kwargs):
        return {
            "ok": True,
            "drive_url": "https://drive.google.com/file/d/recovered-export/view",
            "file_name": "crs_export.xlsx",
            "rows": 12,
            "total": 12,
        }

    monkeypatch.setattr(routes, "DYNAMIC_REPORT_EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(routes, "DYNAMIC_REPORT_EXPORT_JOB_DIR", tmp_path / "exports" / "jobs")
    monkeypatch.setattr(routes, "google_drive_folder_id", fake_drive_folder_id)
    monkeypatch.setattr(DatabaseService, "export_dynamic_report_to_drive", fake_export_to_drive)
    with routes.DYNAMIC_REPORT_EXPORT_JOBS_LOCK:
        routes.DYNAMIC_REPORT_EXPORT_JOBS.clear()

    with TestClient(app) as client:
        login(client)
        started = client.post(
            "/api/reports/export-jobs",
            json={"ma_bao_cao": "CRS", "filters": {}, "page": 1, "page_size": 20},
        )
        assert started.status_code == 200
        job_id = started.json()["job_id"]

        status_body = {}
        for _ in range(80):
            status_response = client.get(f"/api/reports/export-jobs/{job_id}")
            assert status_response.status_code == 200
            status_body = status_response.json()
            if status_body["status"] == "complete":
                break
            time.sleep(0.05)

        assert status_body["status"] == "complete"
        with routes.DYNAMIC_REPORT_EXPORT_JOBS_LOCK:
            routes.DYNAMIC_REPORT_EXPORT_JOBS.clear()

        recovered = client.get(f"/api/reports/export-jobs/{job_id}")
        assert recovered.status_code == 200
        recovered_body = recovered.json()
        assert recovered_body["status"] == "complete"
        assert recovered_body["drive_url"] == "https://drive.google.com/file/d/recovered-export/view"
        assert recovered_body["download_url"] == recovered_body["drive_url"]


def test_dynamic_report_drive_export_sends_compiled_sql_to_internal_api() -> None:
    captured = {}

    class FakeInternalApi:
        settings = get_settings()

        def export_sql_report_to_drive(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True, "drive_url": "https://drive.google.com/file/d/sql-export/view", "rows": 2, "total": 2}

    class FakeRepository:
        def get_sql_report_by_code(self, code):
            return {
                "ten_bao_cao": "CRS",
                "ma_bao_cao": "CRS",
                "cau_lenh_sql": "SELECT ma_tb, ten_tb FROM css_cto.db_thuebao WHERE trang_thai = :STATUS;",
                "cac_tham_so": ["STATUS"],
            }

        def get_sql_report_by_id(self, report_id):
            return None

        def list_sql_reports(self):
            return []

    service = DatabaseService(FakeInternalApi(), FakeRepository())
    result = service.export_dynamic_report_to_drive(
        ma_bao_cao="CRS",
        filters={"STATUS": "1", "IGNORED": "x"},
        search="nguyen",
        search_columns=["TEN_TB"],
        drive_folder_id="drive-folder-001",
        file_name="crs.xlsx",
    )

    assert result["ok"] is True
    assert captured["drive_folder_id"] == "drive-folder-001"
    assert captured["file_name"] == "crs.xlsx"
    assert captured["page_size"] == 5000
    assert captured["max_rows"] >= 1000000
    assert captured["tham_so"]["STATUS"] == "1"
    assert "SEARCH_TERM_1" in captured["tham_so"]
    assert "SELECT * FROM (" in captured["cau_lenh_sql"]
    assert result["ignored_filters"] == ["IGNORED"]


def test_admin_can_manage_and_run_onebss_report(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "start_onebss_otp_mobile_gateway_request",
        lambda *args, **kwargs: {
            "ok": False,
            "status": "otp_required",
            "message": "May tram dang doi OTP.",
            "otp_request_id": "OTP-WORKER-001",
        },
    )
    monkeypatch.setattr(routes, "match_onebss_mobile_gateway_manual_otp", lambda *args, **kwargs: {"ok": True, "status": "matched"})
    monkeypatch.setattr(routes, "consume_onebss_mobile_gateway_otp", lambda *args, **kwargs: {"ok": True, "status": "matched", "otp": "123456"})
    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_bao_cao": "Bien dong PTTB",
            "danh_sach_bien": ["P_TUNGAY", "P_DENNGAY"],
            "parameters": {"P_TUNGAY": "{{month_start}}", "P_DENNGAY": "{{today}}"},
            "otp_service_code": "otp_onebss",
            "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST&name=Test",
            "storage_link": "https://drive.google.com/drive/folders/test-folder",
        }
        created = client.post("/api/admin/onebss-reports", json=payload)
        assert created.status_code == 200
        code = created.json()["ma_bao_cao"]
        assert code.startswith("ONEBSS")

        configs = client.get("/api/onebss-reports/configs")
        assert configs.status_code == 200
        report = next(item for item in configs.json()["reports"] if item["ma_bao_cao"] == code)
        assert report["danh_sach_bien"] == ["P_TUNGAY", "P_DENNGAY"]
        assert report["parameters"] == {"P_TUNGAY": "{{month_start}}", "P_DENNGAY": "{{today}}"}
        assert report["otp_service_code"] == "otp_onebss"

        first_run = client.post(
            "/api/onebss-reports/run",
            json={"ma_bao_cao": code},
        )
        assert first_run.status_code == 200
        assert first_run.json()["status"] == "queued"
        job_id = first_run.json()["job_id"]

        headers = {"Authorization": "Bearer test-worker-token"}
        claim = client.post("/api/onebss-worker/tasks/claim", json={"worker_id": "ws-01"}, headers=headers)
        assert claim.status_code == 200
        task = claim.json()["task"]
        assert task["run_id"] == job_id
        assert task["parameters"] == payload["parameters"]

        waiting_otp = client.post(
            f"/api/onebss-worker/tasks/{job_id}/status",
            json={"status": "otp_required", "message": "Can OTP", "worker_id": "ws-01", "worker_session_id": "worker-session-001"},
            headers=headers,
        )
        assert waiting_otp.status_code == 200
        assert waiting_otp.json()["otp_request_id"] == "OTP-WORKER-001"

        otp_submit = client.post(
            f"/api/onebss-reports/jobs/{job_id}/otp",
            json={"otp": "123456", "otp_request_id": "OTP-WORKER-001", "otp_source": "manual"},
        )
        assert otp_submit.status_code == 200
        assert otp_submit.json()["ok"] is True

        worker_otp = client.get(f"/api/onebss-worker/tasks/{job_id}/otp", headers=headers)
        assert worker_otp.status_code == 200
        assert worker_otp.json()["otp"] == "123456"

        finished = client.post(
            f"/api/onebss-worker/tasks/{job_id}/result",
            json={
                "ok": True,
                "status": "success",
                "message": "Da tai bao cao OneBSS va upload Google Drive.",
                "file_name": "onebss.xlsx",
                "storage_link": "https://drive.google.com/file/d/onebss-file/view",
                "storage_status": "uploaded_google_drive:onebss-file",
                "duration_ms": 1234,
            },
            headers=headers,
        )
        assert finished.status_code == 200
        assert finished.json()["run"]["status"] == "success"

        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["storage_link"] == "https://drive.google.com/file/d/onebss-file/view"

        cleared = client.delete(f"/api/onebss-reports/runs?ma_bao_cao={code}")
        assert cleared.status_code == 200
        assert cleared.json()["deleted"] == 1
        runs_after_clear = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert runs_after_clear == []
        post_clear = client.post(f"/api/onebss-reports/runs/clear?ma_bao_cao={code}")
        assert post_clear.status_code == 200
        assert post_clear.json()["deleted"] == 0


def test_save_onebss_report_ignores_audit_log_failure(monkeypatch) -> None:
    class FakeRepository:
        def get_user_by_id(self, user_id):
            return {"id": user_id, "username": "admin", "full_name": "Admin", "role": "admin", "is_active": True}

        def get_user_permissions(self, user_id):
            return []

        def generate_onebss_report_code(self):
            return "ONEBSS9999"

        def save_onebss_report(self, *args, **kwargs):
            self.saved_args = args
            return 123

        def add_audit_log(self, *args, **kwargs):
            raise RuntimeError("audit_logs unavailable")

    repository = FakeRepository()

    with TestClient(app) as client:
        login(client)
        monkeypatch.setattr(routes, "build_app_repository", lambda: repository)
        response = client.post(
            "/api/admin/onebss-reports",
            json={
                "ma_bao_cao": "MYTV_KTT",
                "ten_bao_cao": "DS MyTV không tương tác",
                "danh_sach_bien": ["p_phanvung_id", "p_nhanvienkd_id"],
                "parameters": {
                    "p_phanvung_id": {"$each": ["13", "47", "66"]},
                    "p_nhanvienkd_id": "0",
                    "$merge_excel": {"sheet": "DATA", "source_column": "p_phanvung_id"},
                },
                "otp_service_code": "onebss",
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=KHAC%2FBRCD%2FRP_BSS_107195&name=Test",
                "storage_link": "https://drive.google.com/drive/folders/test-folder",
            },
        )

    assert response.status_code == 200
    assert response.json()["id"] == 123
    assert repository.saved_args[1] == "MYTV_KTT"
    assert repository.saved_args[4]["p_phanvung_id"]["$each"] == ["13", "47", "66"]


def test_onebss_login_deviceid_screen_requests_otp() -> None:
    from app.application.onebss_report_service import (
        handle_onebss_otp_request,
        pop_onebss_session,
        close_browser_stack,
    )

    class FakeBodyLocator:
        def __init__(self, page):
            self.page = page

        def inner_text(self, timeout=0):
            return self.page.body_text

    class FakePage:
        url = "https://onebss.vnpt.vn/#/auth/login?username=quyennt.cto&deviceId=12345"

        def __init__(self):
            self.body_text = "Xac nhan gui yeu cau"
            self.waits = 0

        def locator(self, selector):
            assert selector == "body"
            return FakeBodyLocator(self)

        def wait_for_load_state(self, *args, **kwargs):
            self.waits += 1

        def wait_for_timeout(self, *args, **kwargs):
            self.waits += 1

    class FakeHelper:
        def __init__(self):
            self.clicks = 0

        def _click_button_text(self, page, texts):
            self.clicks += 1
            page.body_text = "Nhap ma OTP"
            return True

    class FakeClosable:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class FakePlaywright:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    page = FakePage()
    helper = FakeHelper()
    browser = FakeClosable()
    context = FakeClosable()
    playwright = FakePlaywright()

    result = handle_onebss_otp_request(
        page,
        helper,
        playwright,
        browser,
        context,
        {"ma_bao_cao": "TEST"},
        {"P_DENNGAY": "{{today}}"},
        "admin",
    )

    assert result is not None
    assert result["status"] == "otp_required"
    assert result["session_id"]
    assert helper.clicks == 1
    pending = pop_onebss_session(result["session_id"])
    assert pending is not None
    close_browser_stack(pending.browser, pending.context, pending.playwright)
    assert browser.closed is True
    assert context.closed is True
    assert playwright.stopped is True


def test_onebss_mobile_gateway_default_filter_matches_vnpt_sms() -> None:
    from app.modules.mobile_gateway.otp_service import OtpService
    from app.modules.mobile_gateway.repository import MobileGatewayRepository
    from app.modules.mobile_gateway.schemas import SmsMessageIn

    with TestClient(app) as client:
        login(client)
        repository = MobileGatewayRepository(routes.build_app_repository(), get_settings())
        config = repository.get_otp_configuration("onebss")
        onebss_filter = next(item for item in repository.list_otp_filters("onebss", enabled_only=True) if item["filter_id"] == "onebss")
        assert config["sender_pattern"] == "VNPT"
        assert onebss_filter["sender_pattern"] == "VNPT"
        assert onebss_filter["start_prefix"] == ""

        service = OtpService(repository)
        request = service.create_request("onebss", job_id="onebss-vnpt-test")
        inserted, skipped = repository.save_sms_messages(
            "test-device-onebss",
            [
                SmsMessageIn(
                    external_id=f"vnpt-{request['request_id']}",
                    sender="VNPT",
                    body="Ma OTP dang nhap OneBSS cua Quy khach la 654321. Tran trong.",
                    received_at=repository.now(),
                )
            ],
        )
        assert skipped == 0
        assert inserted
        matched = service.match_incoming_sms(inserted[0])
        assert matched is not None
        assert service.consume_code(request["request_id"]) == "654321"


def test_onebss_mobile_gateway_request_uses_latest_otp_received_before_request() -> None:
    from app.modules.mobile_gateway.otp_service import OtpService
    from app.modules.mobile_gateway.repository import MobileGatewayRepository
    from app.modules.mobile_gateway.schemas import SmsMessageIn

    with TestClient(app) as client:
        login(client)
        repository = MobileGatewayRepository(routes.build_app_repository(), get_settings())
        service = OtpService(repository)
        inserted, skipped = repository.save_sms_messages(
            "test-device-onebss-latest",
            [
                SmsMessageIn(
                    external_id=f"vnpt-latest-before-request-{time.time()}",
                    sender="VNPT",
                    body="Ma OTP dang nhap OneBSS cua Quy khach la 987654. Tran trong.",
                    received_at=repository.now(),
                )
            ],
        )
        assert skipped == 0
        assert inserted
        latest = service.record_latest_from_sms(inserted[0])
        assert latest is not None

        request = service.create_request("onebss", job_id="onebss-latest-before-request")

        assert service.consume_code(request["request_id"]) == "987654"
        consumed = repository.get_otp_request(request["request_id"])
        assert consumed is not None
        assert consumed["status"] == "consumed"


def test_onebss_mobile_gateway_resolver_auto_submits_otp(monkeypatch) -> None:
    from app.application import onebss_report_service as service

    events = {}

    class FakeRepository:
        def __init__(self, base_repository, settings):
            events["repository_created"] = True

        def get_otp_configuration(self, service_code):
            assert service_code == "otp_onebss"
            return {"manual_fallback_enabled": True, "auto_fill_enabled": True, "wait_timeout_seconds": 3}

    class FakeOtpService:
        def __init__(self, repository):
            events["otp_service_created"] = True

        def create_request(self, service_code, job_id=""):
            events["service_code"] = service_code
            events["job_id"] = job_id
            return {"request_id": "OTP-AUTO-001"}

        def wait_for_code(self, request_id, timeout_seconds):
            events["request_id"] = request_id
            events["timeout_seconds"] = timeout_seconds
            return "654321"

    def fake_continue(settings, session_id, otp, parameters):
        events["continued"] = (session_id, otp, parameters)
        return {"ok": True, "status": "success", "message": "auto otp ok", "parameters": parameters}

    monkeypatch.setattr(service, "MobileGatewayRepository", FakeRepository)
    monkeypatch.setattr(service, "OtpService", FakeOtpService)
    monkeypatch.setattr(service, "build_repository", lambda settings=None: object())
    monkeypatch.setattr(service, "continue_onebss_api_session", fake_continue)

    result = service.resolve_onebss_otp_with_mobile_gateway(
        get_settings(),
        "api-session-001",
        {"P_DENNGAY": "11/07/2026"},
        otp_service_code="otp_onebss",
    )

    assert result["ok"] is True
    assert events["service_code"] == "otp_onebss"
    assert events["job_id"] == "api-session-001"
    assert events["request_id"] == "OTP-AUTO-001"
    assert events["timeout_seconds"] == 3
    assert events["continued"] == ("api-session-001", "654321", {"P_DENNGAY": "11/07/2026"})


def test_onebss_mobile_gateway_request_returns_without_blocking(monkeypatch) -> None:
    from app.application import onebss_report_service as service

    events = {}

    class FakeRepository:
        def __init__(self, base_repository, settings):
            events["repository_created"] = True

        def get_otp_configuration(self, service_code):
            assert service_code == "otp_onebss"
            return {"manual_fallback_enabled": True, "auto_fill_enabled": True, "wait_timeout_seconds": 90}

    class FakeOtpService:
        def __init__(self, repository):
            events["otp_service_created"] = True

        def create_request(self, service_code, job_id=""):
            events["service_code"] = service_code
            events["job_id"] = job_id
            return {"request_id": "OTP-POLL-001"}

        def wait_for_code(self, request_id, timeout_seconds):
            raise AssertionError("start_onebss_otp_mobile_gateway_request must not block waiting for OTP")

    monkeypatch.setattr(service, "MobileGatewayRepository", FakeRepository)
    monkeypatch.setattr(service, "OtpService", FakeOtpService)
    monkeypatch.setattr(service, "build_repository", lambda settings=None: object())

    result = service.start_onebss_otp_mobile_gateway_request(
        get_settings(),
        "api-session-002",
        {"P_DENNGAY": "12/07/2026"},
        otp_service_code="otp_onebss",
    )

    assert result["ok"] is False
    assert result["status"] == "otp_required"
    assert result["session_id"] == "api-session-002"
    assert result["otp_request_id"] == "OTP-POLL-001"
    assert events["service_code"] == "otp_onebss"
    assert events["job_id"] == "api-session-002"


def test_onebss_mobile_gateway_poll_consumes_matched_otp(monkeypatch) -> None:
    from app.application import onebss_report_service as service

    events = {}

    class FakeRepository:
        def __init__(self, base_repository, settings):
            events["repository_created"] = True

        def expire_otp_requests(self):
            events["expired_checked"] = True

        def get_otp_request(self, request_id):
            events["request_id"] = request_id
            return {
                "request_id": request_id,
                "status": "matched",
                "matched_source_type": "sms",
                "matched_source_id": "42",
                "matched_at": "2026-07-12T08:00:00",
            }

    class FakeOtpService:
        def __init__(self, repository):
            events["otp_service_created"] = True

        def consume_code(self, request_id):
            events["consumed"] = request_id
            return "654321"

    monkeypatch.setattr(service, "MobileGatewayRepository", FakeRepository)
    monkeypatch.setattr(service, "OtpService", FakeOtpService)
    monkeypatch.setattr(service, "build_repository", lambda settings=None: object())

    result = service.consume_onebss_mobile_gateway_otp(get_settings(), "OTP-POLL-001")

    assert result["ok"] is True
    assert result["status"] == "matched"
    assert result["otp"] == "654321"
    assert result["source_type"] == "sms"
    assert result["source_id"] == "42"
    assert events["expired_checked"] is True
    assert events["consumed"] == "OTP-POLL-001"


def test_onebss_otp_request_poll_route_reports_matched_without_consuming(monkeypatch) -> None:
    def fake_inspect(settings, request_id):
        assert request_id == "OTP-POLL-001"
        return {"ok": True, "status": "matched", "code_masked": "******", "source_type": "sms"}

    monkeypatch.setattr(routes, "inspect_onebss_mobile_gateway_otp", fake_inspect)

    with TestClient(app) as client:
        login(client)
        response = client.get("/api/onebss-reports/otp-requests/OTP-POLL-001")

    assert response.status_code == 200
    assert response.json()["status"] == "matched"
    assert "otp" not in response.json()


def test_onebss_worker_consumes_otp_bound_to_request_id(monkeypatch) -> None:
    calls = []

    def fake_consume(settings, request_id):
        assert request_id == "OTP-POLL-001"
        calls.append(("consume", request_id))
        return {"ok": True, "status": "matched", "otp": "654321", "source_type": "sms"}

    def fake_inspect(settings, request_id):
        assert request_id == "OTP-POLL-001"
        calls.append(("inspect", request_id))
        return {"ok": True, "status": "matched", "code_masked": "******", "source_type": "sms"}

    monkeypatch.setattr(routes, "inspect_onebss_mobile_gateway_otp", fake_inspect)
    monkeypatch.setattr(routes, "consume_onebss_mobile_gateway_otp", fake_consume)

    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/onebss-reports",
            json={
                "ten_bao_cao": "Bien dong PTTB",
                "parameters": {"P_DENNGAY": "12/07/2026"},
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST&name=Test",
            },
        )
        assert created.status_code == 200
        queued = client.post(
            "/api/onebss-reports/run",
            json={
                "ma_bao_cao": created.json()["ma_bao_cao"],
            },
        )
        assert queued.status_code == 200
        job_id = queued.json()["job_id"]
        response = client.post(
            f"/api/onebss-reports/jobs/{job_id}/otp",
            json={"otp_request_id": "OTP-POLL-001", "otp_source": "auto"},
        )
        worker_response = client.get(
            f"/api/onebss-worker/tasks/{job_id}/otp",
            headers={"Authorization": "Bearer test-worker-token"},
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert worker_response.status_code == 200
    assert worker_response.json()["otp"] == "654321"
    assert calls == [("inspect", "OTP-POLL-001"), ("consume", "OTP-POLL-001")]


def test_onebss_auth_transition_waits_for_delayed_otp() -> None:
    from app.application.onebss_report_service import page_contains, wait_for_onebss_auth_transition

    class FakeBodyLocator:
        def __init__(self, page):
            self.page = page

        def inner_text(self, timeout=0):
            self.page.reads += 1
            if self.page.reads < 4:
                return "Dang nhap"
            return "XAC THUC OTP"

    class FakePage:
        def __init__(self):
            self.reads = 0
            self.waits = 0

        def locator(self, selector):
            assert selector == "body"
            return FakeBodyLocator(self)

        def wait_for_timeout(self, timeout):
            self.waits += 1

    class FakeHelper:
        def _is_login_page(self, page):
            return True

    page = FakePage()
    wait_for_onebss_auth_transition(page, FakeHelper(), timeout_ms=3000)

    assert page.waits >= 1
    assert page_contains(page, ["OTP"]) is True


def test_onebss_each_parameter_builds_multiple_payloads() -> None:
    from app.application.onebss_report_service import build_onebss_parameter_runs

    runs, merge_config, each_keys = build_onebss_parameter_runs(
        {
            "P_PHANVUNG_ID": {"$each": ["13", "14", "15"]},
            "P_LOAI_NGAY": "1",
            "P_TUNGAY": "01/07/2026",
            "P_DENNGAY": "09/07/2026",
            "baocao_id": 41668,
            "$merge_excel": {"mode": "append", "sheet": "DATA", "source_column": "P_PHANVUNG_ID"},
        }
    )

    assert each_keys == ["P_PHANVUNG_ID"]
    assert merge_config["sheet"] == "DATA"
    assert [run.parameters["P_PHANVUNG_ID"] for run in runs] == ["13", "14", "15"]
    assert all("$merge_excel" not in run.parameters for run in runs)
    assert all("baocao_id" not in run.parameters for run in runs)
    assert all("$each" not in run.parameters["P_PHANVUNG_ID"] for run in runs)


def test_onebss_report_id_uses_configured_meta_value() -> None:
    from app.application.onebss_report_service import OneBssApiToken, onebss_export_parameters, onebss_report_id

    token = OneBssApiToken(
        access_token="token",
        token_type="Bearer",
        username="test@vnpt.vn",
        mobile_id="mobile",
        device_id="device",
        expires_at=9999999999,
    )
    parameters = {"$baocao_id": 41668, "baocao_id": 123, "P_PHANVUNG_ID": "13"}

    assert onebss_report_id({"report_url": "https://onebss.vnpt.vn/#/report/bi?path=UNKNOWN"}, parameters, token) == 41668
    assert onebss_export_parameters(parameters) == {"P_PHANVUNG_ID": "13"}


def test_onebss_download_falls_back_when_grid_has_no_rows(monkeypatch, tmp_path) -> None:
    from app.application import onebss_report_service as service
    from app.application.onebss_report_service import OneBssDownloadError, OneBssDownloadedFile, OneBssApiToken

    events = []
    token = OneBssApiToken(
        access_token="token",
        token_type="Bearer",
        username="test@vnpt.vn",
        mobile_id="mobile",
        device_id="device",
        expires_at=9999999999,
    )

    def fake_grid(*args, **kwargs):
        events.append("grid")
        raise OneBssDownloadError("OneBSS run_v7 grid khong co du lieu")

    def fake_export(settings, token, report, parameters, **kwargs):
        events.append("export")
        target = kwargs.get("target_file") or tmp_path / "fallback.xlsx"
        target.write_bytes(b"PK\x03\x04")
        return OneBssDownloadedFile(
            file_path=target,
            suggested_filename="fallback.xlsx",
            export_info={"params": parameters},
            parameters=parameters,
            source_values=kwargs.get("source_values") or {},
        )

    monkeypatch.setattr(service, "download_onebss_grid_file_api", fake_grid)
    monkeypatch.setattr(service, "download_onebss_export_file_api", fake_export)

    result = service.download_onebss_report_file_api(
        get_settings(),
        token,
        {"report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST&name=Test"},
        {"P_PHANVUNG_ID": "13", "$download_source": "grid"},
    )

    assert events == ["grid", "export"]
    assert result.suggested_filename == "fallback.xlsx"


def test_onebss_download_uses_grid_by_default(monkeypatch, tmp_path) -> None:
    from app.application import onebss_report_service as service
    from app.application.onebss_report_service import OneBssDownloadedFile, OneBssApiToken

    events = []
    token = OneBssApiToken(
        access_token="token",
        token_type="Bearer",
        username="test@vnpt.vn",
        mobile_id="mobile",
        device_id="device",
        expires_at=9999999999,
    )

    def fake_grid(settings, token, report, parameters, **kwargs):
        events.append("grid")
        target = kwargs.get("target_file") or tmp_path / "grid.xlsx"
        target.write_bytes(b"PK\x03\x04")
        return OneBssDownloadedFile(
            file_path=target,
            suggested_filename="grid.xlsx",
            export_info={"params": parameters},
            parameters=parameters,
            source_values=kwargs.get("source_values") or {},
        )

    def fake_export(*args, **kwargs):
        events.append("export")
        raise AssertionError("Default OneBSS download should try grid before Excel export")

    monkeypatch.setattr(service, "download_onebss_grid_file_api", fake_grid)
    monkeypatch.setattr(service, "download_onebss_export_file_api", fake_export)

    result = service.download_onebss_report_file_api(
        get_settings(),
        token,
        {"report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST&name=Test"},
        {"P_PHANVUNG_ID": "13"},
    )

    assert events == ["grid"]
    assert result.suggested_filename == "grid.xlsx"


def test_onebss_excel_export_405_falls_back_to_grid(monkeypatch, tmp_path) -> None:
    from app.application import onebss_report_service as service
    from app.application.onebss_report_service import OneBssDownloadError, OneBssDownloadedFile, OneBssApiToken

    events = []
    token = OneBssApiToken(
        access_token="token",
        token_type="Bearer",
        username="test@vnpt.vn",
        mobile_id="mobile",
        device_id="device",
        expires_at=9999999999,
    )

    def fake_export(*args, **kwargs):
        events.append("export")
        raise OneBssDownloadError("OneBSS khong tra file bao cao. HTTP 405.")

    def fake_grid(settings, token, report, parameters, **kwargs):
        events.append("grid")
        target = kwargs.get("target_file") or tmp_path / "grid.xlsx"
        target.write_bytes(b"PK\x03\x04")
        return OneBssDownloadedFile(
            file_path=target,
            suggested_filename="grid.xlsx",
            export_info={"params": parameters},
            parameters=parameters,
            source_values=kwargs.get("source_values") or {},
        )

    monkeypatch.setattr(service, "download_onebss_export_file_api", fake_export)
    monkeypatch.setattr(service, "download_onebss_grid_file_api", fake_grid)

    result = service.download_onebss_report_file_api(
        get_settings(),
        token,
        {"report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST&name=Test"},
        {"P_PHANVUNG_ID": "13", "$download_source": "excel"},
    )

    assert events == ["export", "grid"]
    assert result.suggested_filename == "grid.xlsx"


def test_onebss_grid_rows_are_written_to_excel(tmp_path) -> None:
    from openpyxl import load_workbook

    from app.application.onebss_report_service import onebss_grid_rows, write_onebss_grid_excel

    rows = onebss_grid_rows({"error_code": "BSS-00000000", "data": [{"MA_TB": "TB1", "DOANH_THU": 10}, {"MA_TB": "TB2", "GOI": "FIBER"}]})
    target = tmp_path / "onebss_grid.xlsx"
    write_onebss_grid_excel(rows, target)

    workbook = load_workbook(target, data_only=True)
    try:
        sheet = workbook["DATA"]
        assert [sheet.cell(row=1, column=index).value for index in range(1, 4)] == ["MA_TB", "DOANH_THU", "GOI"]
        assert sheet.cell(row=2, column=1).value == "TB1"
        assert sheet.cell(row=3, column=3).value == "FIBER"
    finally:
        workbook.close()


def test_onebss_finish_api_splits_regions_and_merges_excel(monkeypatch, tmp_path) -> None:
    from openpyxl import Workbook, load_workbook

    from app.application import onebss_report_service as service
    from app.application.onebss_report_service import OneBssApiToken, OneBssDownloadedFile

    settings = get_settings().model_copy(update={"data_mining_download_dir": str(tmp_path)})
    token = OneBssApiToken(
        access_token="token",
        token_type="Bearer",
        username="test@vnpt.vn",
        mobile_id="mobile",
        device_id="device",
        expires_at=9999999999,
    )
    regions = []

    def fake_download(settings, token, report, parameters, **kwargs):
        region = str(parameters["P_PHANVUNG_ID"])
        regions.append(region)
        target = kwargs.get("target_file") or tmp_path / f"part_{region}.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "DATA"
        sheet.append(["MA_TB", "DOANH_THU"])
        sheet.append([f"TB{region}", int(region)])
        workbook.save(target)
        workbook.close()
        return OneBssDownloadedFile(
            file_path=target,
            suggested_filename=f"part_{region}.xlsx",
            export_info={"report_id": 41668, "title": "Bao cao phat trien moi", "params": parameters},
            parameters=parameters,
            source_values=kwargs.get("source_values") or {},
        )

    monkeypatch.setattr(service, "download_onebss_report_file_api", fake_download)
    monkeypatch.setattr(service, "save_downloaded_file", lambda settings, target, storage: {"ok": True, "storage_link": str(target), "storage_status": "local"})

    result = service.finish_onebss_report_download_api(
        settings,
        token,
        {
            "ma_bao_cao": "ONEBSS_PTM",
            "ten_bao_cao": "Bao cao phat trien moi",
            "report_url": "https://onebss.vnpt.vn/#/report/bi?path=PHATTRIENTHUEBAO%2FBIENDONGPHATTRIENTHUEBAO%2FRP_BSS_28429&name=Test",
        },
        {
            "P_PHANVUNG_ID": {"$each": ["13", "14", "15"]},
            "P_LOAI_NGAY": "1",
            "P_TUNGAY": "01/07/2026",
            "P_DENNGAY": "14/07/2026",
            "$merge_excel": {"sheet": "DATA", "source_column": "P_PHANVUNG_ID"},
        },
    )

    assert result["ok"] is True
    assert result["merged_file_count"] == 3
    assert regions == ["13", "14", "15"]

    workbook = load_workbook(result["file_path"], data_only=True)
    try:
        sheet = workbook["DATA"]
        assert sheet.max_row == 4
        assert [cell.value for cell in sheet[1]] == ["MA_TB", "DOANH_THU", "P_PHANVUNG_ID"]
        assert [sheet.cell(row=row, column=3).value for row in range(2, 5)] == ["13", "14", "15"]
    finally:
        workbook.close()


def test_onebss_finish_api_splits_regions_to_zip_by_default(monkeypatch, tmp_path) -> None:
    import zipfile
    from openpyxl import Workbook

    from app.application import onebss_report_service as service
    from app.application.onebss_report_service import OneBssApiToken, OneBssDownloadedFile

    settings = get_settings().model_copy(update={"data_mining_download_dir": str(tmp_path)})
    token = OneBssApiToken(
        access_token="token",
        token_type="Bearer",
        username="test@vnpt.vn",
        mobile_id="mobile",
        device_id="device",
        expires_at=9999999999,
    )

    def fake_download(settings, token, report, parameters, **kwargs):
        region = str(parameters["P_PHANVUNG_ID"])
        target = kwargs.get("target_file") or tmp_path / f"part_{region}.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["MA_TB"])
        sheet.append([f"TB{region}"])
        workbook.save(target)
        workbook.close()
        return OneBssDownloadedFile(
            file_path=target,
            suggested_filename=f"part_{region}.xlsx",
            export_info={"report_id": 41668, "title": "Bao cao phat trien moi", "params": parameters},
            parameters=parameters,
            source_values=kwargs.get("source_values") or {},
        )

    monkeypatch.setattr(service, "download_onebss_report_file_api", fake_download)
    monkeypatch.setattr(service, "save_downloaded_file", lambda settings, target, storage: {"ok": True, "storage_link": str(target), "storage_status": "local"})

    result = service.finish_onebss_report_download_api(
        settings,
        token,
        {
            "ma_bao_cao": "ONEBSS_PTM",
            "ten_bao_cao": "Bao cao phat trien moi",
            "report_url": "https://onebss.vnpt.vn/#/report/bi?path=PHATTRIENTHUEBAO%2FBIENDONGPHATTRIENTHUEBAO%2FRP_BSS_28429&name=Test",
        },
        {"P_PHANVUNG_ID": {"$each": ["13", "14", "15"]}},
    )

    assert result["ok"] is True
    assert result["output_mode"] == "split_archive"
    assert result["split_file_count"] == 3
    assert result["file_name"].endswith(".zip")
    with zipfile.ZipFile(result["file_path"]) as archive:
        names = archive.namelist()
    assert len(names) == 3
    assert any("P_PHANVUNG_ID_13" in name for name in names)


def test_onebss_merge_excel_files_appends_rows_with_source_column(tmp_path) -> None:
    from openpyxl import Workbook, load_workbook

    from app.application.onebss_report_service import OneBssDownloadedFile, merge_onebss_excel_files

    files = []
    for region, amount in [("13", 100), ("14", 200), ("15", 300)]:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Bao cao"
        sheet.append(["Bao cao phat trien thue bao"])
        sheet.append(["MA_TB", "DOANH_THU"])
        sheet.append([f"TB{region}", amount])
        source = tmp_path / f"region_{region}.xlsx"
        workbook.save(source)
        files.append(
            OneBssDownloadedFile(
                file_path=source,
                suggested_filename=source.name,
                export_info={},
                parameters={"P_PHANVUNG_ID": region},
                source_values={"P_PHANVUNG_ID": region},
            )
        )

    target = tmp_path / "merged.xlsx"
    merge_onebss_excel_files(
        files,
        target,
        {"mode": "append", "sheet": "DATA", "source_column": "P_PHANVUNG_ID"},
        ["P_PHANVUNG_ID"],
    )

    merged = load_workbook(target)
    rows = list(merged["DATA"].values)
    assert rows == [
        ("Bao cao phat trien thue bao", None, None),
        ("MA_TB", "DOANH_THU", "P_PHANVUNG_ID"),
        ("TB13", 100, "13"),
        ("TB14", 200, "14"),
        ("TB15", 300, "15"),
    ]


def test_onebss_report_run_records_worker_errors() -> None:
    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/onebss-reports",
            json={
                "ten_bao_cao": "OneBSS failed run",
                "danh_sach_bien": ["P_TUNGAY"],
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST_FAIL&name=Test",
                "storage_link": "https://drive.google.com/drive/folders/test-folder",
            },
        )
        assert created.status_code == 200
        code = created.json()["ma_bao_cao"]

        response = client.post("/api/onebss-reports/run", json={"ma_bao_cao": code, "parameters": {"P_TUNGAY": "01/07/2026"}})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        failed = client.post(
            f"/api/onebss-worker/tasks/{job_id}/result",
            json={"ok": False, "status": "failed", "message": "browser launch failed"},
            headers={"Authorization": "Bearer test-worker-token"},
        )
        assert failed.status_code == 200
        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "failed"
        assert "browser launch failed" in runs[0]["message"]


def test_onebss_report_run_can_be_cancelled_without_worker_overwrite() -> None:
    with TestClient(app) as client:
        login(client)
        client.delete("/api/onebss-reports/runs")
        created = client.post(
            "/api/admin/onebss-reports",
            json={
                "ten_bao_cao": "OneBSS cancellable run",
                "danh_sach_bien": ["P_TUNGAY"],
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST_CANCEL&name=Test",
                "storage_link": "",
            },
        )
        assert created.status_code == 200
        code = created.json()["ma_bao_cao"]

        response = client.post("/api/onebss-reports/run", json={"ma_bao_cao": code, "parameters": {"P_TUNGAY": "01/07/2026"}})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        headers = {"Authorization": "Bearer test-worker-token"}
        claim = client.post("/api/onebss-worker/tasks/claim", json={"worker_id": "ws-cancel"}, headers=headers)
        assert claim.status_code == 200
        assert claim.json()["task"]["run_id"] == job_id

        cancelled = client.post(f"/api/onebss-reports/runs/{job_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["can_cancel"] is False

        status_update = client.post(
            f"/api/onebss-worker/tasks/{job_id}/status",
            json={"status": "running", "message": "Still running", "worker_id": "ws-cancel"},
            headers=headers,
        )
        assert status_update.status_code == 200
        assert status_update.json()["cancelled"] is True

        finished = client.post(
            f"/api/onebss-worker/tasks/{job_id}/result",
            json={"ok": True, "status": "success", "message": "Should not overwrite cancel"},
            headers=headers,
        )
        assert finished.status_code == 200
        assert finished.json()["run"]["status"] == "cancelled"

        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "cancelled"
        assert runs[0]["can_cancel"] is False


def test_onebss_workstation_worker_updates_existing_status_message(monkeypatch) -> None:
    from scripts import onebss_workstation_worker as worker

    calls = []

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.payload

    class FakeClient:
        def request(self, method: str, path: str, **kwargs):
            calls.append((method, path, kwargs.get("json") or {}))
            return FakeResponse({"ok": True, "run": {"status": "running"}})

    def fake_run_onebss_report_request(settings, report, parameters, **kwargs):
        progress_callback = kwargs["progress_callback"]
        progress_callback("Da dien tai khoan OneBSS.")
        progress_callback("Da dien mat khau OneBSS.")
        progress_callback("Da gui OTP ve dien thoai.")
        progress_callback("Da di den bao cao OneBSS.")
        return {
            "ok": True,
            "status": "success",
            "message": "Da tai bao cao OneBSS.",
            "storage_status": "uploaded_google_drive:test-file",
        }

    monkeypatch.setattr(worker, "run_onebss_report_request", fake_run_onebss_report_request)

    worker.process_task(FakeClient(), {"run_id": "RUN-PROGRESS", "report": {}, "parameters": {}}, "ws-progress", 0)

    messages = [payload.get("message") for _, path, payload in calls if path.endswith("/status")]
    assert "Da dien tai khoan OneBSS." in messages
    assert "Da dien mat khau OneBSS." in messages
    assert "Da gui OTP ve dien thoai." in messages
    assert "Da di den bao cao OneBSS." in messages


def test_onebss_workstation_worker_retries_transient_web_errors(monkeypatch) -> None:
    import httpx
    from scripts import onebss_workstation_worker as worker

    attempts = {"count": 0}
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: None)

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict | None = None) -> None:
            self.status_code = status_code
            self.payload = payload or {}
            self.request = httpx.Request("POST", "https://vnptcto.com/api/onebss-worker/tasks/claim")

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                response = httpx.Response(self.status_code, request=self.request)
                raise httpx.HTTPStatusError("temporary error", request=self.request, response=response)

        def json(self) -> dict:
            return self.payload

    class FakeClient:
        def request(self, method: str, path: str, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                return FakeResponse(502)
            return FakeResponse(200, {"ok": True, "task": None})

    data = worker.request_json(FakeClient(), "POST", "/api/onebss-worker/tasks/claim", json={"worker_id": "ws"})

    assert data == {"ok": True, "task": None}
    assert attempts["count"] == 2


def test_onebss_worker_uploads_result_file_for_download(monkeypatch, tmp_path) -> None:
    settings = get_settings().model_copy(update={"data_mining_download_dir": str(tmp_path)})
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/onebss-reports",
            json={
                "ten_bao_cao": "OneBSS worker upload",
                "danh_sach_bien": ["P_TUNGAY"],
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST_UPLOAD&name=Test",
                "storage_link": "",
            },
        )
        assert created.status_code == 200
        code = created.json()["ma_bao_cao"]

        response = client.post("/api/onebss-reports/run", json={"ma_bao_cao": code, "parameters": {"P_TUNGAY": "01/07/2026"}})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        headers = {"Authorization": "Bearer test-worker-token"}
        upload = client.post(
            f"/api/onebss-worker/tasks/{job_id}/file",
            files={"file": ("result.zip", b"zip-bytes", "application/zip")},
            headers=headers,
        )
        assert upload.status_code == 200
        uploaded = upload.json()["file"]
        assert uploaded["file_name"] == "result.zip"
        assert Path(uploaded["file_path"]).read_bytes() == b"zip-bytes"

        finished = client.post(
            f"/api/onebss-worker/tasks/{job_id}/result",
            json={
                "ok": True,
                "status": "success",
                "message": "Da gui file ve web.",
                "file_name": uploaded["file_name"],
                "file_path": uploaded["file_path"],
                "storage_status": uploaded["storage_status"],
            },
            headers=headers,
        )
        assert finished.status_code == 200
        assert finished.json()["run"]["download_url"]

        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        download = client.get(runs[0]["download_url"])
        assert download.status_code == 200
        assert download.content == b"zip-bytes"


def test_onebss_worker_result_preserves_uploaded_web_file(monkeypatch, tmp_path) -> None:
    settings = get_settings().model_copy(update={"data_mining_download_dir": str(tmp_path)})
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/onebss-reports",
            json={
                "ten_bao_cao": "OneBSS preserve web file",
                "danh_sach_bien": ["P_TUNGAY"],
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST_PRESERVE&name=Test",
                "storage_link": "",
            },
        )
        assert created.status_code == 200
        code = created.json()["ma_bao_cao"]

        response = client.post("/api/onebss-reports/run", json={"ma_bao_cao": code, "parameters": {"P_TUNGAY": "01/07/2026"}})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        headers = {"Authorization": "Bearer test-worker-token"}
        upload = client.post(
            f"/api/onebss-worker/tasks/{job_id}/file",
            files={"file": ("result.xlsx", b"xlsx-bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=headers,
        )
        assert upload.status_code == 200

        finished = client.post(
            f"/api/onebss-worker/tasks/{job_id}/result",
            json={
                "ok": True,
                "status": "success",
                "message": "Worker finished after web upload.",
                "file_name": "",
                "file_path": "",
                "storage_status": "",
            },
            headers=headers,
        )
        assert finished.status_code == 200
        run = finished.json()["run"]
        assert run["file_name"] == "result.xlsx"
        assert run["storage_status"] == "uploaded_worker_file"
        assert run["download_url"]
        download = client.get(run["download_url"])
        assert download.status_code == 200
        assert download.content == b"xlsx-bytes"


def test_onebss_worker_drive_link_does_not_expose_missing_local_download() -> None:
    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/onebss-reports",
            json={
                "ten_bao_cao": "OneBSS Drive link",
                "danh_sach_bien": ["P_TUNGAY"],
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST_DRIVE_LINK&name=Test",
                "storage_link": "",
            },
        )
        assert created.status_code == 200
        code = created.json()["ma_bao_cao"]

        response = client.post("/api/onebss-reports/run", json={"ma_bao_cao": code, "parameters": {"P_TUNGAY": "01/07/2026"}})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        finished = client.post(
            f"/api/onebss-worker/tasks/{job_id}/result",
            json={
                "ok": True,
                "status": "success",
                "message": "Da upload file len Google Drive.",
                "file_name": "result.xlsx",
                "file_path": "C:/VNPTCTO/onebss/result.xlsx",
                "storage_link": "https://drive.google.com/open?id=drive-file-002",
                "storage_status": "uploaded_google_drive",
            },
            headers={"Authorization": "Bearer test-worker-token"},
        )
        assert finished.status_code == 200
        run = finished.json()["run"]
        assert run["storage_link"] == "https://drive.google.com/open?id=drive-file-002"
        assert run["file_url"] == "https://drive.google.com/open?id=drive-file-002"
        assert "download_url" not in run

        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["storage_link"] == "https://drive.google.com/open?id=drive-file-002"
        assert runs[0]["file_url"] == "https://drive.google.com/open?id=drive-file-002"
        assert "download_url" not in runs[0]


def test_onebss_run_derives_drive_link_from_storage_status() -> None:
    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/onebss-reports",
            json={
                "ten_bao_cao": "OneBSS Drive status only",
                "danh_sach_bien": ["P_TUNGAY"],
                "report_url": "https://onebss.vnpt.vn/#/report/bi?path=TEST_DRIVE_STATUS&name=Test",
                "storage_link": "",
            },
        )
        assert created.status_code == 200
        code = created.json()["ma_bao_cao"]

        response = client.post("/api/onebss-reports/run", json={"ma_bao_cao": code, "parameters": {"P_TUNGAY": "01/07/2026"}})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        finished = client.post(
            f"/api/onebss-worker/tasks/{job_id}/result",
            json={
                "ok": True,
                "status": "success",
                "message": "Da upload file len Google Drive.",
                "file_name": "result.xlsx",
                "file_path": "C:/VNPTCTO/onebss/result.xlsx",
                "storage_link": "",
                "storage_status": "uploaded_google_drive:driveFile_003-ABC",
            },
            headers={"Authorization": "Bearer test-worker-token"},
        )
        assert finished.status_code == 200
        run = finished.json()["run"]
        assert run["storage_link"] == "https://drive.google.com/file/d/driveFile_003-ABC/view"
        assert run["file_url"] == "https://drive.google.com/file/d/driveFile_003-ABC/view"
        assert "download_url" not in run

        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["file_url"] == "https://drive.google.com/file/d/driveFile_003-ABC/view"


def test_supabase_onebss_run_uses_parameters_json_column(monkeypatch) -> None:
    captured = {}
    repository = SupabaseRepository("https://example.supabase.co/rest/v1", "secret")

    def fake_insert(table, payload):
        captured["table"] = table
        captured["payload"] = payload
        return payload

    monkeypatch.setattr(repository, "_insert", fake_insert)
    run = repository.save_onebss_report_run({
        "ma_bao_cao": "TEST",
        "ten_bao_cao": "Test",
        "status": "failed",
        "parameters": {"P_TUNGAY": "01/07/2026"},
    })
    assert captured["table"] == "onebss_report_runs"
    assert "parameters_json" in captured["payload"]
    assert "parameters" not in captured["payload"]
    assert run["parameters"] == {"P_TUNGAY": "01/07/2026"}


def test_supabase_onebss_report_save_falls_back_without_otp_service_code(monkeypatch) -> None:
    repository = SupabaseRepository("https://example.supabase.co/rest/v1", "secret")
    payloads = []

    def fake_insert(table, payload):
        payloads.append(payload)
        if "otp_service_code" in payload:
            raise RuntimeError(
                'Supabase REST loi 400: {"code":"PGRST204","message":"Could not find the '
                "'otp_service_code' column of 'onebss_reports' in the schema cache\"}"
            )
        return {"id": 77, **payload}

    monkeypatch.setattr(repository, "_insert", fake_insert)
    report_id = repository.save_onebss_report(
        None,
        "MYTV_KTT",
        "DS MyTV",
        ["p_phanvung_id"],
        {"p_phanvung_id": {"$each": ["13", "47", "66"]}},
        "https://onebss.vnpt.vn/#/report/bi?path=TEST&name=Test",
        "https://drive.google.com/drive/folders/test",
        "onebss",
    )

    assert report_id == 77
    assert "otp_service_code" in payloads[0]
    assert "otp_service_code" not in payloads[1]
    assert payloads[1]["parameters"]["p_phanvung_id"]["$each"] == ["13", "47", "66"]


def test_supabase_clear_onebss_report_runs_uses_run_id(monkeypatch) -> None:
    repository = SupabaseRepository("https://example.supabase.co/rest/v1", "secret")
    calls = []

    def fake_get(table, params):
        calls.append(("get", table, params))
        return [{"run_id": "RUN1"}, {"run_id": "RUN2"}]

    def fake_delete(table, params):
        calls.append(("delete", table, params))

    monkeypatch.setattr(repository, "_get", fake_get)
    monkeypatch.setattr(repository, "_delete", fake_delete)

    assert repository.clear_onebss_report_runs("ONEBSS01") == 2
    assert calls[0] == ("get", "onebss_report_runs", {"select": "run_id", "ma_bao_cao": "eq.ONEBSS01"})
    assert calls[1] == ("delete", "onebss_report_runs", {"ma_bao_cao": "eq.ONEBSS01"})

    calls.clear()
    assert repository.clear_onebss_report_runs() == 2
    assert calls[0] == ("get", "onebss_report_runs", {"select": "run_id"})
    assert calls[1] == ("delete", "onebss_report_runs", {"run_id": "not.is.null"})


def test_dynamic_report_expands_comma_values_for_in_bind_params() -> None:
    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_bao_cao": "Loai hinh IN test",
            "ma_bao_cao": "BC_TEST_LOAIHINH_IN",
            "cau_lenh_sql": "SELECT COUNT(*) AS thuebao FROM V_CHITIET_PTM WHERE loaitb_id in (:LOAIHINH);",
            "cac_tham_so": ["LOAIHINH"],
        }
        assert client.post("/api/admin/sql-reports", json=payload).status_code == 200

        result = client.post(
            "/api/reports/run",
            json={"ma_bao_cao": "BC_TEST_LOAIHINH_IN", "filters": {"LOAIHINH": "61,171,271"}, "page": 1, "page_size": 20},
        )

        assert result.status_code == 200
        assert result.json()["rows"][0]["THAM_SO"] == "LOAIHINH_1=61, LOAIHINH_2=171, LOAIHINH_3=271"


def test_define_sql_is_compiled_with_raw_filter_values() -> None:
    sql = """
DEFINE p_loaihinh = :LOAIHINH
DEFINE p_thang = :MONTH
DEFINE p_donvi = :DONVI
SELECT *
FROM css_cto.db_thuebao
WHERE loaitb_id = '&p_loaihinh'
  AND ('&p_thang' IS NULL OR '&p_thang' = '')
  AND ten_donvi_cha LIKE '&p_donvi';
"""
    compiled, details = DatabaseService._compile_define_sql(
        sql,
        {"LOAIHINH": "58", "MONTH ": "", "DONVI": "VNPT%"},
    )

    assert "DEFINE" not in compiled.upper()
    assert "loaitb_id = '58'" in compiled
    assert "LIKE 'VNPT%'" in compiled
    assert "'' IS NULL OR '' = ''" in compiled
    assert not compiled.endswith(";")
    assert details["define_params"] == ["p_loaihinh", "p_thang", "p_donvi"]
    assert DatabaseService._filters_for_compiled_sql(compiled, {"LOAIHINH": "58", "MONTH": "", "DONVI": "VNPT%"}) == {}


def test_compiled_sql_keeps_only_remaining_bind_params() -> None:
    sql = "SELECT * FROM css_cto.db_thuebao WHERE ngay >= :FROM_DATE AND ten_donvi_cha LIKE '&p_donvi';"
    params = {"FROM_DATE": "2026-05-01", "DONVI": "VNPT%"}

    assert DatabaseService._filters_for_compiled_sql(sql, params) == {"FROM_DATE": "2026-05-01"}


def test_in_bind_param_expands_comma_values() -> None:
    sql = "SELECT COUNT(*) FROM V_CHITIET_PTM WHERE loaitb_id in (:LOAIHINH) AND trangthaitb_id = :STATUS;"
    expanded_sql, filters = DatabaseService._expand_in_list_bind_params(
        sql,
        {"LOAIHINH": "61,171,271", "STATUS": "1"},
    )

    assert "loaitb_id IN (:LOAIHINH_1, :LOAIHINH_2, :LOAIHINH_3)" in expanded_sql
    assert DatabaseService._filters_for_compiled_sql(expanded_sql, filters) == {
        "LOAIHINH_1": "61",
        "LOAIHINH_2": "171",
        "LOAIHINH_3": "271",
        "STATUS": "1",
    }


def test_admin_can_manage_dashboard_layout_and_lazy_load_tab_data(monkeypatch) -> None:
    with TestClient(app) as client:
        login(client)
        report_payload = {
            "ten_bao_cao": "Báo cáo Builder test",
            "ma_bao_cao": "BC_BUILDER_TEST",
            "cau_lenh_sql": "SELECT don_vi, so_luong FROM css_cto.builder_test WHERE trang_thai = :status;",
            "cac_tham_so": ["status"],
        }
        assert client.post("/api/admin/sql-reports", json=report_payload).status_code == 200

        layout_payload = {
            "page_id": "DASHBOARD_TEST_BUILDER",
            "page_name": "Dashboard Test Builder",
            "layout": {
                "page_id": "DASHBOARD_TEST_BUILDER",
                "tabs": [
                    {
                        "tab_id": "tab_a",
                        "tab_name": "Tab A",
                        "order": 1,
                        "grid_layout": [
                            {
                                "row_id": 1,
                                "layout_type": "2_columns",
                                "widgets": [
                                    {
                                        "position": 1,
                                        "type": "bar_chart",
                                        "title": "Widget A",
                                        "sql_code": "BC_BUILDER_TEST",
                                        "filters": {"status": "1"},
                                        "chart_config": {"orientation": "horizontal", "label_column": "don_vi", "value_column": "so_luong"},
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "tab_id": "tab_b",
                        "tab_name": "Tab B",
                        "order": 2,
                        "grid_layout": [
                            {
                                "row_id": 1,
                                "layout_type": "1_column",
                                "widgets": [
                                    {
                                        "position": 1,
                                        "type": "text_title",
                                        "title": "Tiêu đề thiết kế",
                                        "text_content": "Nội dung giới thiệu tab",
                                    }
                                ],
                            },
                            {
                                "row_id": 2,
                                "layout_type": "3_columns",
                                "widgets": [
                                    {
                                        "position": 1,
                                        "type": "combo_chart",
                                        "title": "Biểu đồ kết hợp",
                                        "sql_code": "BC_BUILDER_TEST",
                                        "chart_config": {
                                            "label_column": "don_vi",
                                            "bar_column": "so_luong",
                                            "line_column": "ty_le",
                                        },
                                    },
                                    {
                                        "position": 2,
                                        "type": "data_card",
                                        "title": "Thẻ dữ liệu",
                                        "sql_code": "BC_BUILDER_TEST",
                                        "icon_url": "https://example.vn/icon.png",
                                        "text_content": "Ghi chú thẻ",
                                    },
                                ],
                            }
                        ],
                    },
                ],
            },
        }
        saved = client.post("/api/admin/dashboard-layouts", json=layout_payload)
        assert saved.status_code == 200
        saved_layout = saved.json()["layout"]
        assert saved_layout["tabs"][0]["tab_id"] == "tab_a"
        assert saved_layout["tabs"][0]["grid_layout"][0]["widgets"][0]["chart_config"]["orientation"] == "horizontal"
        assert saved_layout["tabs"][1]["grid_layout"][0]["layout_type"] == "1_column"
        assert saved_layout["tabs"][1]["grid_layout"][0]["widgets"][0]["type"] == "text_title"
        assert saved_layout["tabs"][1]["grid_layout"][1]["layout_type"] == "3_columns"
        assert saved_layout["tabs"][1]["grid_layout"][1]["widgets"][1]["icon_url"] == "https://example.vn/icon.png"

        layouts = client.get("/api/admin/dashboard-layouts")
        assert layouts.status_code == 200
        assert any(item["page_id"] == "DASHBOARD_TEST_BUILDER" for item in layouts.json()["layouts"])

        pages = client.get("/api/admin/dashboard-layout-pages")
        assert pages.status_code == 200
        builder_page = next(page for page in pages.json()["pages"] if page["page_id"] == "DASHBOARD_TEST_BUILDER")
        assert builder_page["feature_code"] == "dashboardtestbuilder"
        assert builder_page["feature_name"] == "Dashboard Test Builder"
        assert builder_page["saved"] is True

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert "dashboardtestbuilder" in me.json()["user"]["permissions"]

        tab_a = client.get("/api/admin/dashboard-layouts/DASHBOARD_TEST_BUILDER/tabs/tab_a/data")
        assert tab_a.status_code == 200
        tab_payload = tab_a.json()
        assert len(tab_payload["widgets"]) == 1
        assert tab_payload["widgets"][0]["sql_code"] == "BC_BUILDER_TEST"
        assert tab_payload["widgets"][0]["data"]["columns"] == ["STT", "MA_BAO_CAO", "TEN_BAO_CAO", "THAM_SO"]
        assert tab_payload["widgets"][0]["data"]["rows"][0]["THAM_SO"] == "status=1"

        api_calls = []
        original_run_sql_report = routes.InternalApiClient.run_sql_report

        def counting_run_sql_report(self, **kwargs):
            api_calls.append((kwargs["ma_bao_cao"], kwargs["tham_so"]))
            return original_run_sql_report(self, **kwargs)

        monkeypatch.setattr(routes.InternalApiClient, "run_sql_report", counting_run_sql_report)
        tab_b = client.get("/api/admin/dashboard-layouts/DASHBOARD_TEST_BUILDER/tabs/tab_b/data")
        assert tab_b.status_code == 200
        assert [widget["type"] for widget in tab_b.json()["widgets"]] == ["combo_chart", "data_card"]
        assert api_calls == [("BC_BUILDER_TEST", {})]

        inverted_report_payload = {
            "ten_bao_cao": "Check_Job",
            "ma_bao_cao": "CHECK JOB DU LIEU",
            "cau_lenh_sql": "SELECT job_name, status FROM css_cto.check_job;",
            "cac_tham_so": [],
        }
        inverted_created = client.post("/api/admin/sql-reports", json=inverted_report_payload)
        assert inverted_created.status_code == 200
        inverted_report_id = inverted_created.json()["id"]
        table_layout_payload = {
            "page_id": "DASHBOARD_CHECK_JOB",
            "page_name": "CHECK_JOB",
            "layout": {
                "page_id": "DASHBOARD_CHECK_JOB",
                "tabs": [
                    {
                        "tab_id": "tab_check",
                        "tab_name": "Tab moi",
                        "order": 1,
                        "grid_layout": [
                            {
                                "row_id": 1,
                                "layout_type": "1_column",
                                "widgets": [
                                    {
                                        "position": 1,
                                        "type": "data_table",
                                        "title": "Check job",
                                        "sql_code": "Check_Job (CHECK JOB DU LIEU)",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        }
        saved_table_layout = client.post("/api/admin/dashboard-layouts", json=table_layout_payload)
        assert saved_table_layout.status_code == 200
        saved_widget = saved_table_layout.json()["layout"]["tabs"][0]["grid_layout"][0]["widgets"][0]
        assert saved_widget["sql_code"] == "CHECK_JOB"
        tab_check = client.get("/api/admin/dashboard-layouts/DASHBOARD_CHECK_JOB/tabs/tab_check/data")
        assert tab_check.status_code == 200
        tab_check_payload = tab_check.json()
        assert tab_check_payload["widgets"][0]["sql_code"] == "CHECK_JOB"
        assert tab_check_payload["widgets"][0]["data"]["ok"] is True
        assert api_calls[-1] == ("CHECK_JOB", {})
        calls_after_cache_fill = len(api_calls)
        tab_check_cached = client.get("/api/admin/dashboard-layouts/DASHBOARD_CHECK_JOB/tabs/tab_check/data")
        assert tab_check_cached.status_code == 200
        cached_data = tab_check_cached.json()["widgets"][0]["data"]
        assert cached_data["ok"] is True
        assert cached_data["details"]["dashboard_cache"]["hit"] is True
        assert len(api_calls) == calls_after_cache_fill
        updated_inverted_report_payload = {
            **inverted_report_payload,
            "id": inverted_report_id,
            "cau_lenh_sql": "SELECT job_name, status, run_time FROM css_cto.check_job;",
        }
        assert client.post("/api/admin/sql-reports", json=updated_inverted_report_payload).status_code == 200
        tab_check_after_sql_update = client.get("/api/admin/dashboard-layouts/DASHBOARD_CHECK_JOB/tabs/tab_check/data")
        assert tab_check_after_sql_update.status_code == 200
        assert len(api_calls) == calls_after_cache_fill + 1
        assert "dashboard_cache" not in tab_check_after_sql_update.json()["widgets"][0]["data"].get("details", {})
        refresh_result = DatabaseService(routes.InternalApiClient(routes.get_settings()), routes.build_app_repository()).refresh_dashboard_chart_cache(page_id="DASHBOARD_CHECK_JOB")
        assert refresh_result["deleted_stale"] == 0

        empty_check_layout_payload = {
            **table_layout_payload,
            "layout": {
                "page_id": "DASHBOARD_CHECK_JOB",
                "tabs": [
                    {
                        "tab_id": "tab_check",
                        "tab_name": "Tab moi",
                        "order": 1,
                        "grid_layout": [],
                    }
                ],
            },
        }
        assert client.post("/api/admin/dashboard-layouts", json=empty_check_layout_payload).status_code == 200
        refresh_after_delete = DatabaseService(routes.InternalApiClient(routes.get_settings()), routes.build_app_repository()).refresh_dashboard_chart_cache(page_id="DASHBOARD_CHECK_JOB")
        assert refresh_after_delete["deleted_stale"] == 1

        short_code_report_payload = {
            "ten_bao_cao": "Check_Job_Table",
            "ma_bao_cao": "CHECK",
            "cau_lenh_sql": "SELECT job_name, status FROM css_cto.check_job;",
            "cac_tham_so": [],
        }
        assert client.post("/api/admin/sql-reports", json=short_code_report_payload).status_code == 200
        legacy_layout_payload = {
            "page_id": "DASHBOARD_CHECK_JOB_LEGACY",
            "page_name": "CHECK_JOB",
            "layout": {
                "page_id": "DASHBOARD_CHECK_JOB_LEGACY",
                "tabs": [
                    {
                        "tab_id": "tab_check",
                        "tab_name": "DANH SACH JOB",
                        "order": 1,
                        "grid_layout": [
                            {
                                "row_id": 1,
                                "layout_type": "1_column",
                                "widgets": [
                                    {
                                        "position": 1,
                                        "type": "data_table",
                                        "title": "Check_Job_Table",
                                        "sql_code": "CHECK_JOB_TABLE",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        }
        assert client.post("/api/admin/dashboard-layouts", json=legacy_layout_payload).status_code == 200
        legacy_tab = client.get("/api/admin/dashboard-layouts/DASHBOARD_CHECK_JOB_LEGACY/tabs/tab_check/data")
        assert legacy_tab.status_code == 200
        legacy_payload = legacy_tab.json()
        assert legacy_payload["ok"] is True
        assert legacy_payload["widgets"][0]["data"]["ok"] is True
        assert api_calls[-1] == ("CHECK", {})

        group_payload = {
            "page_id": "DASHBOARD_EMPTY_GROUP",
            "page_name": "NhÃ³m Dashboard rá»—ng",
            "layout": {
                "page_id": "DASHBOARD_EMPTY_GROUP",
                "tabs": [
                    {
                        "tab_id": "tab_group",
                        "tab_name": "NhÃ³m",
                        "order": 1,
                        "grid_layout": [],
                    }
                ],
            },
        }
        group_saved = client.post("/api/admin/dashboard-layouts", json=group_payload)
        assert group_saved.status_code == 200
        assert group_saved.json()["layout"]["tabs"][0]["grid_layout"] == []
        group_tab = client.get("/api/admin/dashboard-layouts/DASHBOARD_EMPTY_GROUP/tabs/tab_group/data")
        assert group_tab.status_code == 200
        assert group_tab.json()["widgets"] == []

        fiber_report = {
            "ten_bao_cao": "Fiber PTM",
            "ma_bao_cao": "FIBER_PTM",
            "cau_lenh_sql": "SELECT * FROM css_cto.fiber WHERE loaihinh = :LOAIHINH AND ngay = :SYSDATE AND donvi LIKE :DONVI;",
            "cac_tham_so": ["LOAIHINH", "SYSDATE", "DONVI"],
        }
        assert client.post("/api/admin/sql-reports", json=fiber_report).status_code == 200
        result = client.post(
            "/api/reports/run",
            json={
                "ma_bao_cao": "FIBER_PTM",
                "filters": {"loaihinh": "58", "sysdate": "SYSDATE", "donvi": "VNPT%"},
                "page": 1,
                "page_size": 20,
            },
        )
        assert result.status_code == 200
        assert result.json()["rows"][0]["THAM_SO"] == "LOAIHINH=58, SYSDATE=SYSDATE, DONVI=VNPT%"


def test_dashboard_layout_tab_uses_bulk_chart_cache_for_cached_widgets() -> None:
    class FakeSettings:
        dashboard_chart_cache_enabled = True
        dashboard_chart_cache_report_ids = "*"
        dashboard_chart_cache_report_codes = "*"
        dashboard_chart_cache_ttl_seconds = 300
        dashboard_tab_max_workers = 10

    class FakeInternalApi:
        settings = FakeSettings()

        def __init__(self) -> None:
            self.calls = []

        def run_sql_report(self, **kwargs):
            self.calls.append(kwargs)
            return {"ok": True, "columns": [], "rows": []}

    class FakeRepository:
        def __init__(self) -> None:
            self.bulk_calls = []
            self.single_reads = []
            self.layout = {
                "tabs": [
                    {
                        "tab_id": "tab_cache",
                        "grid_layout": [
                            {
                                "row_id": 1,
                                "widgets": [
                                    {
                                        "position": 1,
                                        "type": "bar_chart",
                                        "title": "Report A",
                                        "sql_code": "REPORT_A",
                                        "report_id": 1,
                                        "filters": {},
                                    },
                                    {
                                        "position": 2,
                                        "type": "metric",
                                        "title": "Report B",
                                        "sql_code": "REPORT_B",
                                        "report_id": 2,
                                        "filters": {"status": "1"},
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
            self.reports = [
                {"id": 1, "ma_bao_cao": "REPORT_A", "ten_bao_cao": "Report A"},
                {"id": 2, "ma_bao_cao": "REPORT_B", "ten_bao_cao": "Report B"},
            ]
            self.cache_by_key = {}
            for report, filters in ((self.reports[0], {}), (self.reports[1], {"status": "1"})):
                chart_key = DatabaseService.dashboard_chart_cache_key(
                    report_id=report["id"],
                    sql_code=report["ma_bao_cao"],
                    filters=filters,
                    report_code=report["ma_bao_cao"],
                )
                self.cache_by_key[chart_key] = {
                    "chart_key": chart_key,
                    "status": "success",
                    "payload": {
                        "ok": True,
                        "columns": ["TEN_BAO_CAO"],
                        "rows": [{"TEN_BAO_CAO": report["ten_bao_cao"]}],
                    },
                    "refreshed_at": "2026-06-26T00:00:00+00:00",
                    "expires_at": "2026-06-26T00:05:00+00:00",
                }

        def get_dashboard_layout(self, page_id):
            return {"page_id": page_id, "layout": self.layout}

        def list_sql_reports(self):
            return self.reports

        def get_dashboard_chart_cache_many(self, chart_keys):
            self.bulk_calls.append(list(chart_keys))
            return [self.cache_by_key[key] for key in chart_keys if key in self.cache_by_key]

        def get_dashboard_chart_cache(self, chart_key):
            self.single_reads.append(chart_key)
            return self.cache_by_key.get(chart_key)

    internal_api = FakeInternalApi()
    repository = FakeRepository()
    result = DatabaseService(internal_api, repository).run_dashboard_layout_tab(page_id="DASHBOARD_CACHE", tab_id="tab_cache")

    assert result["ok"] is True
    assert len(result["widgets"]) == 2
    assert len(repository.bulk_calls) == 1
    assert len(repository.bulk_calls[0]) == 2
    assert repository.single_reads == []
    assert internal_api.calls == []
    assert all(widget["data"]["details"]["dashboard_cache"]["hit"] is True for widget in result["widgets"])


def test_dashboard_layout_pages_include_overview_and_reports_not_web_admin() -> None:
    with TestClient(app) as client:
        login(client)
        web_layout = {
            "page_id": "ADMIN_USERS",
            "page_name": "Quan tri nguoi dung",
            "layout": {
                "page_id": "ADMIN_USERS",
                "tabs": [
                    {
                        "tab_id": "tab_admin_users",
                        "tab_name": "Admin users",
                        "order": 1,
                        "grid_layout": [
                            {"row_id": 1, "layout_type": "2_columns", "widgets": []}
                        ],
                    }
                ],
            },
        }
        assert client.post("/api/admin/dashboard-layouts", json=web_layout).status_code == 200

        response = client.get("/api/admin/dashboard-layout-pages")
        assert response.status_code == 200
        pages = response.json()["pages"]
        page_ids = [page["page_id"] for page in pages]

        assert "DASHBOARD_KINH_DOANH" not in page_ids
        assert "REPORTS" not in page_ids
        assert "ADMIN_USERS" in page_ids

        generated_admin_page = next(page for page in pages if page["page_id"] == "ADMIN_USERS")
        assert generated_admin_page["feature_code"] == "adminusers"
        assert generated_admin_page["saved"] is True
        assert not any(page["feature_code"] == "admin.users" for page in pages)
        assert not any(page["feature_code"] == "admin_users" for page in pages)

        features = client.get("/api/admin/features").json()["features"]
        reports_feature = next(feature for feature in features if feature["code"] == "truyvansql")
        new_reports_feature = next(feature for feature in features if feature["code"] == "baocaomoi")
        builder_feature = next(feature for feature in features if feature["code"] == "thietkelayoutbaocao")
        generated_feature = next(feature for feature in features if feature["code"] == "adminusers")
        assert reports_feature["name"] == "Truy vấn SQL"
        assert new_reports_feature["name"] == "Báo cáo mới"
        assert builder_feature["parent_code"] == "baocaomoi"
        assert generated_feature["parent_code"] == "baocaomoi"
        moved_features = []
        for feature in features:
            item = {
                "code": feature["code"],
                "name": feature["name"],
                "parent_code": feature.get("parent_code"),
                "sort_order": feature.get("sort_order") or 0,
            }
            if item["code"] == "adminusers":
                item["parent_code"] = "quantriweb"
                item["sort_order"] = 999
            moved_features.append(item)
        assert client.put("/api/admin/features/layout", json={"features": moved_features}).status_code == 200

        moved_pages = client.get("/api/admin/dashboard-layout-pages").json()["pages"]
        moved_admin_page = next(page for page in moved_pages if page["page_id"] == "ADMIN_USERS")
        assert moved_admin_page["feature_code"] == "adminusers"
        assert moved_admin_page["saved"] is True

        assert client.post("/api/admin/dashboard-layouts", json=web_layout).status_code == 200
        refreshed_features = client.get("/api/admin/features").json()["features"]
        refreshed_admin_feature = next(feature for feature in refreshed_features if feature["code"] == "adminusers")
        assert refreshed_admin_feature["parent_code"] == "quantriweb"


def test_admin_can_create_root_menu_and_assign_dashboard_layout_to_it() -> None:
    with TestClient(app) as client:
        login(client)
        menu_response = client.post("/api/admin/features/menu", json={"name": "Menu doanh thu"})
        assert menu_response.status_code == 200
        menu_feature = menu_response.json()["feature"]
        assert menu_feature["code"] == "menudoanhthu"
        assert menu_feature["parent_code"] is None

        layout_payload = {
            "page_id": "DASHBOARD_MENU_CHILD",
            "page_name": "Dashboard menu con",
            "parent_code": menu_feature["code"],
            "layout": {
                "tabs": [
                    {
                        "tab_id": "tab_menu_child",
                        "tab_name": "Menu con",
                        "grid_layout": [
                            {"row_id": 1, "layout_type": "2_columns", "widgets": []},
                        ],
                    }
                ],
            },
        }
        saved = client.post("/api/admin/dashboard-layouts", json=layout_payload)
        assert saved.status_code == 200
        assert saved.json()["parent_code"] == menu_feature["code"]

        features = client.get("/api/admin/features").json()["features"]
        layout_feature = next(feature for feature in features if feature["code"] == "dashboardmenuchild")
        assert layout_feature["parent_code"] == menu_feature["code"]

        pages = client.get("/api/admin/dashboard-layout-pages").json()["pages"]
        saved_page = next(page for page in pages if page["page_id"] == "DASHBOARD_MENU_CHILD")
        assert saved_page["parent_code"] == menu_feature["code"]

        detail = client.get("/api/admin/dashboard-layouts/DASHBOARD_MENU_CHILD")
        assert detail.status_code == 200
        assert detail.json()["parent_code"] == menu_feature["code"]


def test_dashboard_layout_delete_keeps_page_as_unsaved_and_aliases_duplicate_codes() -> None:
    with TestClient(app) as client:
        login(client)
        layout_payload = {
            "page_id": "DASHBOARD_DELETE_ME",
            "page_name": "Dashboard Delete Me",
            "layout": {
                "page_id": "DASHBOARD_DELETE_ME",
                "tabs": [
                    {
                        "tab_id": "tab_delete",
                        "tab_name": "Tab delete",
                        "order": 1,
                        "grid_layout": [],
                    }
                ],
            },
        }
        assert client.post("/api/admin/dashboard-layouts", json=layout_payload).status_code == 200
        assert client.delete("/api/admin/dashboard-layouts/DASHBOARD_DELETE_ME").status_code == 200
        pages = client.get("/api/admin/dashboard-layout-pages").json()["pages"]
        deleted_page = next(page for page in pages if page["feature_code"] == "dashboarddeleteme")
        assert deleted_page["saved"] is False
        assert deleted_page["unsaved"] is True
        assert client.delete(f"/api/admin/dashboard-layout-pages/{deleted_page['feature_code']}").status_code == 200
        purged_pages = client.get("/api/admin/dashboard-layout-pages").json()["pages"]
        assert not any(page["feature_code"] == "dashboarddeleteme" for page in purged_pages)

        assert client.post("/api/admin/dashboard-layouts", json=layout_payload).status_code == 200
        saved_pages = client.get("/api/admin/dashboard-layout-pages").json()["pages"]
        saved_page = next(page for page in saved_pages if page["page_id"] == "DASHBOARD_DELETE_ME")
        assert client.delete(f"/api/admin/dashboard-layout-pages/{saved_page['feature_code']}").status_code == 400

    pages = routes.build_dashboard_layout_pages(
        [
            {"code": "baocaomoi", "name": "Bao cao moi", "parent_code": None, "sort_order": 1},
            {"code": "dashboard_tong_quan", "name": "Tong quan cu", "parent_code": "baocaomoi", "sort_order": 2},
            {"code": "dashboardtongquan", "name": "Tong quan moi", "parent_code": "baocaomoi", "sort_order": 3},
        ],
        [
            {"page_id": "DASHBOARD_TONG_QUAN", "page_name": "Tong quan", "created_at": None, "updated_at": None},
        ],
    )
    assert [page["page_id"] for page in pages].count("DASHBOARD_TONG_QUAN") == 1


def test_viewer_cannot_access_dashboard_builder_api_or_report_runner() -> None:
    with TestClient(app) as client:
        login(client)
        created = client.post(
            "/api/admin/users",
            json={
                "username": "viewer_builder",
                "full_name": "Viewer Builder",
                "password": "Viewer@Builder123",
                "role": "viewer",
            },
        )
        assert created.status_code == 200
        client.post("/api/auth/logout")
        login(client, "viewer_builder", "Viewer@Builder123")
        home = client.get("/")
        assert home.status_code == 200
        assert "view-dashboard-builder" not in home.text
        assert "dashboard-designed-section" in home.text

        forbidden_urls = [
            "/api/admin/dashboard-layouts",
            "/api/admin/dashboard-layout-pages",
            "/api/admin/dashboard-layouts/DASHBOARD_TEST_BUILDER",
            "/api/admin/dashboard-layouts/DASHBOARD_TEST_BUILDER/tabs/tab_a/data",
            "/api/reports/configs",
        ]
        for url in forbidden_urls:
            response = client.get(url)
            assert response.status_code == 403
            assert response.json()["detail"] == "Bạn không có quyền truy cập chức năng này"

        run_response = client.post(
            "/api/reports/run",
            json={"ma_bao_cao": "BC_BUILDER_TEST", "filters": {}, "page": 1, "page_size": 20},
        )
        assert run_response.status_code == 403
        assert run_response.json()["detail"] == "Bạn không có quyền truy cập chức năng này"


def test_auto_module_is_removed_from_dashboard() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.get("/")
        assert response.status_code == 200
        assert "data-feature-code=\"auto\"" not in response.text
        assert "attt" not in response.text.lower()


def test_admin_can_create_viewer_and_viewer_cannot_access_admin_api() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.post(
            "/api/admin/users",
            json={
                "username": "viewer_test",
                "full_name": "Người xem thử nghiệm",
                "password": "Viewer@Test123",
                "role": "viewer",
            },
        )
        assert response.status_code == 200
        client.post("/api/auth/logout")
        login(client, "viewer_test", "Viewer@Test123")
        assert client.get("/api/admin/users").status_code == 403


def test_admin_can_manage_catalog_and_encrypted_web_credentials() -> None:
    with TestClient(app) as client:
        login(client)
        website = client.post(
            "/api/admin/websites",
            json={"name": "VNPT Test", "url": "https://example.vn", "requires_otp": True, "is_active": True},
        )
        assert website.status_code == 200
        website_id = website.json()["website"]["id"]
        saved = client.post(
            "/api/credentials",
            json={"website_id": website_id, "login_username": "user01", "password": "Secret@Test123", "notes": ""},
        )
        assert saved.status_code == 200
        credentials = client.get("/api/credentials").json()["credentials"]
        assert credentials[0]["requires_otp"] == 1
        assert "encrypted_password" not in credentials[0]
        revealed = client.post(f"/api/credentials/{credentials[0]['id']}/reveal")
        assert revealed.json()["password"] == "Secret@Test123"


def test_viewer_needs_feature_permission_for_vault() -> None:
    with TestClient(app) as client:
        login(client)
        users = client.get("/api/admin/users").json()["users"]
        viewer = next(user for user in users if user["username"] == "viewer_test")
        client.post("/api/auth/logout")
        login(client, "viewer_test", "Viewer@Test123")
        assert client.get("/api/credentials").status_code == 403
        client.post("/api/auth/logout")
        login(client)
        response = client.put(
            f"/api/admin/users/{viewer['id']}/permissions",
            json={"feature_codes": ["taikhoanweb", "xemdanhsachtaikhoan", "themvasuataikhoan", "xemmatkhaudaluu"]},
        )
        assert response.status_code == 200
        client.post("/api/auth/logout")
        login(client, "viewer_test", "Viewer@Test123")
        assert client.get("/api/credentials").status_code == 200


def test_dashboard_layout_preserves_google_sheet_embed_without_sql() -> None:
    with TestClient(app) as client:
        login(client)
        layout_payload = {
            "page_id": "DASHBOARD_GOOGLE_SHEET",
            "page_name": "Google Sheet Dashboard",
            "layout": {
                "page_id": "DASHBOARD_GOOGLE_SHEET",
                "tabs": [
                    {
                        "tab_id": "tab_sheet",
                        "tab_name": "Sheet",
                        "order": 1,
                        "grid_layout": [
                            {
                                "row_id": 1,
                                "layout_type": "1_column",
                                "widgets": [
                                    {
                                        "position": 1,
                                        "type": "google_sheet_embed",
                                        "title": "Published Sheet",
                                        "chart_config": {
                                            "embed_url": "https://docs.google.com/spreadsheets/d/e/2PACX-test/pubhtml",
                                            "embed_height": "560",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        }

        saved = client.post("/api/admin/dashboard-layouts", json=layout_payload)
        assert saved.status_code == 200
        widget = saved.json()["layout"]["tabs"][0]["grid_layout"][0]["widgets"][0]
        assert widget["type"] == "google_sheet_embed"
        assert widget["sql_code"] == ""
        assert widget["chart_config"]["embed_url"].startswith("https://docs.google.com/spreadsheets/")

        reopened = client.get("/api/admin/dashboard-layouts/DASHBOARD_GOOGLE_SHEET")
        assert reopened.status_code == 200
        reopened_widget = reopened.json()["layout"]["tabs"][0]["grid_layout"][0]["widgets"][0]
        assert reopened_widget["type"] == "google_sheet_embed"
        assert reopened_widget["chart_config"]["embed_height"] == "560"

        tab_data = client.get("/api/admin/dashboard-layouts/DASHBOARD_GOOGLE_SHEET/tabs/tab_sheet/data")
        assert tab_data.status_code == 200
        assert tab_data.json()["ok"] is True
        assert tab_data.json()["widgets"] == []


def test_google_sheet_table_extractor_removes_sheet_headers() -> None:
    extractor = routes.GoogleSheetTableExtractor()
    extractor.feed(
        """
        <style>.s0{background:#fee;color:#111}.row-headers-background{background:#073763;color:#fff}</style>
        <table class="waffle">
          <tbody>
            <tr><th class="row-headers-background">1</th><td class="s0">A</td></tr>
            <tr><th class="row-headers-background">2</th><td class="s0">B</td></tr>
          </tbody>
        </table>
        """
    )
    html = extractor.sanitized_html()
    assert 'class="google-sheet-table-source ritz grid-container"' in html
    assert '<th class="row-headers-background"' not in html
    assert ">1<" not in html
    assert ">2<" not in html
    assert ">A<" in html
    assert ">B<" in html
