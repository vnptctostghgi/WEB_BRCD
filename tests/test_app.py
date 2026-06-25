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

from app.application.database_service import DatabaseService
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
        assert client.post("/api/admin/sql-reports", json=inverted_report_payload).status_code == 200
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
        assert "dashboard-designed-section" not in home.text

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
