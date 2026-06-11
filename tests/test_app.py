import os
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

from app.main import app
from app.presentation import routes


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
        assert "Quản trị người dùng" in response.text


def test_favicon_redirects_to_system_logo() -> None:
    with TestClient(app) as client:
        response = client.get("/favicon.ico", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/images/system-logo.png"


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
            "cau_lenh_sql": "SELECT ma_tb, ten_tb FROM css_cto.db_thuebao WHERE trang_thai = :status",
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
            json={"feature_codes": ["vault", "vault.view", "vault.manage", "vault.reveal"]},
        )
        assert response.status_code == 200
        client.post("/api/auth/logout")
        login(client, "viewer_test", "Viewer@Test123")
        assert client.get("/api/credentials").status_code == 200
