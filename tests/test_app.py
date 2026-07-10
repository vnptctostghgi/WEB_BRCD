import os
import json
from datetime import datetime
from pathlib import Path

os.environ["DB_MOCK_MODE"] = "true"
os.environ["INTERNAL_API_MOCK_MODE"] = "true"
os.environ["INTERNAL_API_URL"] = "http://10.92.17.88:8000/api/du-lieu-web"
os.environ["APP_DATABASE_BACKEND"] = "sqlite"
os.environ["APP_DATABASE_PATH"] = "data/test_app.db"
os.environ["INITIAL_ADMIN_USERNAME"] = "admin"
os.environ["INITIAL_ADMIN_PASSWORD"] = "Admin@Brcd2026!"

test_database = Path("data/test_app.db")
test_database.unlink(missing_ok=True)

from fastapi.testclient import TestClient

from app.application.database_service import DatabaseService
from app.data_access.supabase_repository import SupabaseRepository
from app.main import app
from app.presentation import routes
from app.settings import get_settings


def login(client: TestClient, username: str = "admin", password: str = "Admin@Brcd2026!") -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_unauthenticated_user_is_redirected_to_login() -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_admin_can_login_and_open_dashboard() -> None:
    with TestClient(app) as client:
        login(client)
        response = client.get("/")
        assert response.status_code == 200
        assert 'rel="icon" type="image/png" href="/static/images/system-logo.png"' in response.text
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
        assert response.headers["cache-control"] == "public, max-age=604800"


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


def test_public_telegram_alert_test_route(monkeypatch) -> None:
    sent_messages = []

    def fake_send_message(self, title, message, details=None):
        sent_messages.append((title, message, details))
        return True

    monkeypatch.setattr("app.presentation.routes.TelegramNotifier.send_message", fake_send_message)
    with TestClient(app) as client:
        response = client.get("/api/test/telegram-alert")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert sent_messages[0][0] == "TEST Telegram"
        assert "[TEST]" in sent_messages[0][1]


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


def test_admin_can_manage_data_mining_schedules_and_run_now(monkeypatch) -> None:
    calls = []

    def fake_run_data_mining_schedule(repository, settings, schedule, **kwargs):
        calls.append({
            "schedule_id": schedule["schedule_id"],
            "otp": kwargs.get("otp"),
            "created_by": kwargs.get("created_by"),
            "parameter_overrides": kwargs.get("parameter_overrides"),
        })
        run = repository.create_data_mining_run(schedule["schedule_id"], schedule.get("parameters"), created_by=kwargs.get("created_by") or "")
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
        assert calls[-1]["otp"] == "123456"
        assert calls[-1]["parameter_overrides"] == {"P_DENNGAY": "09/07/2026"}

        runs = client.get(f"/api/admin/data-mining/runs?schedule_id={schedule['schedule_id']}").json()["runs"]
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


def test_admin_can_manage_and_run_onebss_report(monkeypatch) -> None:
    calls = []

    def fake_run_onebss_report_request(settings, report, parameters, **kwargs):
        calls.append({
            "report": report["ma_bao_cao"],
            "parameters": parameters,
            "otp": kwargs.get("otp"),
            "session_id": kwargs.get("session_id"),
        })
        if not kwargs.get("session_id"):
            return {
                "ok": False,
                "status": "otp_required",
                "message": "OneBSS yeu cau OTP.",
                "session_id": "otp-session-001",
                "parameters": parameters,
            }
        return {
            "ok": True,
            "status": "success",
            "message": "Da tai bao cao OneBSS va upload Google Drive.",
            "file_name": "onebss.xlsx",
            "file_path": "data/data_mining_downloads/onebss.xlsx",
            "storage_link": "https://drive.google.com/file/d/onebss-file/view",
            "storage_status": "uploaded_google_drive:onebss-file",
            "parameters": parameters,
            "duration_ms": 1234,
        }

    monkeypatch.setattr(routes, "run_onebss_report_request", fake_run_onebss_report_request)
    with TestClient(app) as client:
        login(client)
        payload = {
            "ten_bao_cao": "Bien dong PTTB",
            "danh_sach_bien": ["P_TUNGAY", "P_DENNGAY"],
            "parameters": {"P_TUNGAY": "{{month_start}}", "P_DENNGAY": "{{today}}"},
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

        first_run = client.post(
            "/api/onebss-reports/run",
            json={"ma_bao_cao": code},
        )
        assert first_run.status_code == 200
        assert first_run.json()["status"] == "otp_required"
        assert first_run.json()["session_id"] == "otp-session-001"
        assert calls[-1]["parameters"] == payload["parameters"]

        second_run = client.post(
            "/api/onebss-reports/run",
            json={
                "ma_bao_cao": code,
                "session_id": "otp-session-001",
                "otp": "123456",
            },
        )
        assert second_run.status_code == 200
        assert second_run.json()["ok"] is True
        assert calls[-1]["otp"] == "123456"
        assert calls[-1]["parameters"] == payload["parameters"]
        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["storage_link"] == "https://drive.google.com/file/d/onebss-file/view"


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


def test_onebss_report_run_records_unhandled_errors(monkeypatch) -> None:
    def failing_run_onebss_report_request(settings, report, parameters, **kwargs):
        raise RuntimeError("browser launch failed")

    monkeypatch.setattr(routes, "run_onebss_report_request", failing_run_onebss_report_request)
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
        data = response.json()
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "browser launch failed" in data["message"]
        runs = client.get(f"/api/onebss-reports/runs?ma_bao_cao={code}").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "failed"


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
