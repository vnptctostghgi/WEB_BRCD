from pathlib import Path
import sqlite3
from io import BytesIO
from typing import Literal

import openpyxl
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.application.auth_service import AuthService
from app.application.database_service import DatabaseService
from app.application.vault_service import VaultService
from app.application.connection_service import ConnectionService
from app.application.openvpn_service import openvpn_service
from app.application.oracle_pool import oracle_pool_service
from app.application.telegram_notifier import TelegramNotifier
from app.data_access.app_repository import AppRepository
from app.data_access.repository_factory import build_repository
from app.data_access.oracle_repository import OracleRepository
from app.settings import get_settings


router = APIRouter()
templates = Jinja2Templates(directory=Path("app/presentation/templates"))
FAILED_LOGIN_COUNTS: dict[str, int] = {}


class LoginPayload(BaseModel):
    username: str
    password: str


class CreateUserPayload(BaseModel):
    username: str
    full_name: str
    password: str
    role: Literal["admin", "viewer"]


class UpdateUserPayload(BaseModel):
    full_name: str
    role: Literal["admin", "viewer"]
    is_active: bool


class PasswordPayload(BaseModel):
    password: str


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str


class WebsitePayload(BaseModel):
    id: int | None = None
    name: str
    url: str
    requires_otp: bool = False
    is_active: bool = True


class CredentialPayload(BaseModel):
    id: int | None = None
    website_id: int
    login_username: str
    password: str
    notes: str = ""


class PermissionPayload(BaseModel):
    feature_codes: list[str]


class BulkPermissionPayload(BaseModel):
    user_ids: list[int]
    feature_codes: list[str]


class BulkDataPermissionPayload(BaseModel):
    user_ids: list[int]
    region_codes: list[str]


class DataRegionPayload(BaseModel):
    code: str
    name: str
    is_active: bool = True
    sort_order: int = 0


class SystemConnectionPayload(BaseModel):
    name: str
    connection_type: str
    description: str = ""
    config: dict = {}
    is_active: bool = False


class SystemRolePayload(BaseModel):
    code: str
    name: str
    description: str = ""
    is_active: bool = True
    sort_order: int = 0


class FeatureLayoutItem(BaseModel):
    code: str
    name: str
    parent_code: str | None = None
    sort_order: int = 0


class FeatureLayoutPayload(BaseModel):
    features: list[FeatureLayoutItem]


class WorkTaskPayload(BaseModel):
    task_id: str = ""
    ten_cong_viec: str
    type: Literal["Daily", "Weekly", "Once"] = "Daily"
    time: str = "07:00"
    weekday: str = ""
    once_date: str = ""
    group: str = ""
    check: bool = False


def build_app_repository() -> AppRepository:
    return build_repository(get_settings())


def build_auth_service() -> AuthService:
    return AuthService(build_app_repository())


def build_database_service() -> DatabaseService:
    settings = get_settings()
    return DatabaseService(OracleRepository(settings))


def build_vault_service() -> VaultService:
    settings = get_settings()
    return VaultService(build_app_repository(), settings.session_secret.get_secret_value())


def build_connection_service() -> ConnectionService:
    settings = get_settings()
    return ConnectionService(build_app_repository(), settings)


def notify_if_failed(title: str, result: dict, extra: dict | None = None) -> None:
    if result.get("ok"):
        return
    settings = get_settings()
    details = extra or {}
    connection_name = result.get("connection_name")
    if connection_name:
        details = {**details, "ket_noi": connection_name}
    TelegramNotifier(settings).send_message(title, result.get("message", "Không rõ lỗi."), details or None)


def raise_work_task_schema_error(error: RuntimeError) -> None:
    if "work_tasks" in str(error):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supabase chưa có bảng work_tasks. Hãy chạy lại file sql/supabase_upgrade_admin_modules.sql.",
        ) from error
    raise error


def notify_login_failed_threshold(request: Request, username: str) -> None:
    display_username = username.strip() or "unknown"
    counter_key = display_username.lower()
    failures = FAILED_LOGIN_COUNTS.get(counter_key, 0) + 1
    FAILED_LOGIN_COUNTS[counter_key] = failures
    if failures >= 5:
        client_host = request.client.host if request.client else "unknown"
        sent = TelegramNotifier(get_settings()).send_message(
            "Canh bao dang nhap sai",
            f"Tai khoan {display_username} dang nhap sai {failures} lan lien tiep.",
            {"ip": client_host, "nguong_canh_bao": 5, "so_lan_sai": failures},
        )
        try:
            build_app_repository().add_audit_log(
                "system",
                "telegram_login_alert_sent" if sent else "telegram_login_alert_failed",
                f"Login failed alert for {display_username}: {failures} failures",
            )
        except Exception:
            pass


def reset_failed_login_counter(username: str) -> None:
    FAILED_LOGIN_COUNTS.pop((username.strip() or "unknown").lower(), None)


def normalize_email_username(email: str) -> str:
    return (email or "").strip().split("@", 1)[0].lower()


def normalize_cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_employee_workbook(content: bytes) -> list[dict]:
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    headers = [normalize_cell(cell.value).upper() for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    index = {header: position for position, header in enumerate(headers)}
    required = ["MÃ NHÂN VIÊN", "TÊN NHÂN VIÊN", "THƯ ĐIỆN TỬ"]
    if not all(column in index for column in required):
        raise ValueError("File Excel thiếu cột MÃ NHÂN VIÊN, TÊN NHÂN VIÊN hoặc THƯ ĐIỆN TỬ.")
    employees = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        employee_code = normalize_cell(row[index["MÃ NHÂN VIÊN"]])
        full_name = normalize_cell(row[index["TÊN NHÂN VIÊN"]])
        email = normalize_cell(row[index["THƯ ĐIỆN TỬ"]]).lower()
        if not employee_code and not full_name and not email:
            continue
        employees.append({
            "employee_code": employee_code,
            "full_name": full_name,
            "email": email,
            "phone": normalize_cell(row[index.get("SỐ ĐIỆN THOẠI", -1)]) if "SỐ ĐIỆN THOẠI" in index else "",
            "birth_date": normalize_cell(row[index.get("NGÀY SINH", -1)])[:10] if "NGÀY SINH" in index else "",
            "gender": normalize_cell(row[index.get("GIỚI TÍNH", -1)]) if "GIỚI TÍNH" in index else "",
            "department": normalize_cell(row[index.get("PHÒNG BAN", -1)]) if "PHÒNG BAN" in index else "",
            "job_title": normalize_cell(row[index.get("VTCV", -1)]) if "VTCV" in index else "",
        })
    return employees



def current_user(request: Request) -> dict:
    session_user = request.session.get("user")
    if not session_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn chưa đăng nhập.")
    user = build_app_repository().get_user_by_id(int(session_user["id"]))
    if not user or not user["is_active"]:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không còn hợp lệ.")
    public = AuthService.public_user(user)
    public["permissions"] = build_app_repository().get_user_permissions(public["id"])
    return public


def admin_user(request: Request) -> dict:
    user = current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền quản trị.")
    return user


def require_feature(request: Request, feature_code: str) -> dict:
    user = current_user(request)
    if user["role"] == "admin":
        return user
    if feature_code not in build_app_repository().get_user_permissions(user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn chưa được cấp quyền sử dụng chức năng này.")
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    if request.session.get("user"):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"app_name": get_settings().app_name},
    )


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return RedirectResponse("/static/images/system-logo.png", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> Response:
    try:
        user = current_user(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": get_settings().app_name, "user": user},
    )


@router.post("/api/auth/login")
def login(request: Request, payload: LoginPayload) -> dict:
    user = build_auth_service().authenticate(payload.username, payload.password)
    if not user:
        notify_login_failed_threshold(request, payload.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tên đăng nhập hoặc mật khẩu không đúng.")
    reset_failed_login_counter(payload.username)
    request.session.clear()
    request.session["user"] = user
    return {"ok": True, "user": user}


@router.post("/api/auth/logout")
def logout(request: Request) -> dict:
    user = request.session.get("user")
    if user:
        build_app_repository().add_audit_log(user["username"], "logout", "Đăng xuất")
    request.session.clear()
    return {"ok": True}


@router.get("/api/auth/me")
def me(request: Request) -> dict:
    return {"user": current_user(request)}


@router.post("/api/auth/change-password")
def change_password(request: Request, payload: ChangePasswordPayload) -> dict:
    user = current_user(request)
    try:
        build_auth_service().change_own_password(
            user["id"], user["username"], payload.current_password, payload.new_password
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    user["must_change_password"] = 0
    request.session["user"] = user
    return {"ok": True, "message": "Đổi mật khẩu thành công."}


@router.get("/api/health/database")
def database_health(request: Request) -> dict:
    current_user(request)
    result = build_database_service().get_connection_status()
    notify_if_failed("Lỗi kết nối Oracle", result)
    return result


@router.get("/api/system/status")
def system_status(request: Request) -> dict:
    current_user(request)
    settings = get_settings()
    return {
        "vpn": openvpn_service.status(),
        "database_pool": oracle_pool_service.status(),
        "query_policy": {
            "select_star_allowed": False,
            "pagination_required": True,
            "page_size_min": 20,
            "page_size_max": 50,
            "connect_timeout_ms": settings.oracle_connect_timeout_ms,
            "query_timeout_ms": settings.oracle_query_timeout_ms,
        },
    }


@router.get("/api/admin/users")
def list_users(request: Request) -> dict:
    admin_user(request)
    return {"users": build_app_repository().list_users()}


@router.post("/api/admin/users")
def create_user(request: Request, payload: CreateUserPayload) -> dict:
    actor = admin_user(request)
    try:
        user = build_auth_service().create_user(
            actor["username"], payload.username, payload.full_name, payload.password, payload.role
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"ok": True, "user": user}


@router.get("/api/admin/users/import-template")
def download_user_import_template(request: Request) -> Response:
    admin_user(request)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "NguoiDung"
    sheet.append(["MÃ NHÂN VIÊN", "TÊN NHÂN VIÊN", "SỐ ĐIỆN THOẠI", "THƯ ĐIỆN TỬ", "NGÀY SINH", "GIỚI TÍNH", "PHÒNG BAN", "VTCV"])
    sheet.append(["VNPT008888", "Nguyen Van A", "0912345678", "vana@vnpt.vn", "1990-01-01", "Nam", "Phong kinh doanh", "Nhan vien"])
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="mau_import_nguoi_dung.xlsx"'},
    )


@router.post("/api/admin/users/import")
async def import_users(request: Request, file: UploadFile = File(...)) -> dict:
    actor = admin_user(request)
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chỉ hỗ trợ file Excel .xlsx.")
    try:
        employees = parse_employee_workbook(await file.read())
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    repository = build_app_repository()
    auth_service = AuthService(repository)
    created = []
    skipped = []
    for employee in employees:
        username = normalize_email_username(employee["email"])
        if not employee["employee_code"] or not employee["full_name"] or not username:
            skipped.append({"employee_code": employee.get("employee_code"), "reason": "Thiếu mã nhân viên, họ tên hoặc email."})
            continue
        try:
            existing_user = repository.get_user_by_employee_or_email(employee["employee_code"], employee["email"])
        except RuntimeError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
        if existing_user:
            skipped.append({"employee_code": employee["employee_code"], "reason": "Mã nhân viên hoặc email đã tồn tại."})
            continue
        try:
            user = auth_service.create_user(actor["username"], username, employee["full_name"], employee["employee_code"], "viewer", employee)
            created.append(user)
        except (ValueError, sqlite3.IntegrityError, RuntimeError) as error:
            skipped.append({"employee_code": employee["employee_code"], "reason": str(error)})
    repository.add_audit_log(actor["username"], "users_imported", f"Import users: created={len(created)}, skipped={len(skipped)}")
    return {"ok": True, "created_count": len(created), "skipped_count": len(skipped), "created": created, "skipped": skipped}


@router.put("/api/admin/users/{user_id}")
def update_user(request: Request, user_id: int, payload: UpdateUserPayload) -> dict:
    actor = admin_user(request)
    try:
        user = build_auth_service().update_user(
            actor["username"], actor["id"], user_id, payload.full_name, payload.role, payload.is_active
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"ok": True, "user": user}


@router.delete("/api/admin/users/{user_id}")
def delete_user(request: Request, user_id: int) -> dict:
    actor = admin_user(request)
    user = build_app_repository().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")
    if user["id"] == actor["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bạn không thể tự xóa tài khoản đang đăng nhập.")
    if user["role"] == "admin" and build_app_repository().count_active_admins() <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hệ thống phải còn ít nhất một admin.")
    build_app_repository().delete_user(user_id)
    build_app_repository().add_audit_log(actor["username"], "user_deleted", f"Xoa user {user['username']}")
    return {"ok": True}


@router.post("/api/admin/users/{user_id}/reset-password")
def reset_password(request: Request, user_id: int, payload: PasswordPayload) -> dict:
    actor = admin_user(request)
    try:
        build_auth_service().reset_password(actor["username"], user_id, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"ok": True, "message": "Đặt lại mật khẩu thành công."}


@router.get("/api/admin/audit-logs")
def audit_logs(request: Request) -> dict:
    admin_user(request)
    return {"logs": build_app_repository().list_audit_logs()}


@router.get("/api/admin/system")
def system_info(request: Request) -> dict:
    admin_user(request)
    settings = get_settings()
    users = build_app_repository().list_users()
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "oracle_host": settings.db_host,
        "oracle_service": settings.db_service,
        "storage_backend": settings.app_database_backend,
        "supabase_rest_url": settings.supabase_rest_url,
        "user_count": len(users),
        "active_user_count": sum(1 for user in users if user["is_active"]),
    }


@router.get("/api/admin/storage/health")
def storage_health(request: Request) -> dict:
    admin_user(request)
    repository = build_app_repository()
    if hasattr(repository, "health_check"):
        return repository.health_check()
    return {"ok": True, "backend": "sqlite"}


@router.get("/api/admin/connections")
def system_connections(request: Request) -> dict:
    admin_user(request)
    connections = build_app_repository().list_system_connections()
    for connection in connections:
        config = connection.get("config", {})
        connection["config"] = {
            key: value for key, value in config.items()
            if "pass" not in key.lower() and "secret" not in key.lower() and "key" not in key.lower()
        }
        if config.get("secret_ref"):
            connection["secret_ref"] = config["secret_ref"]
    return {"connections": connections}


@router.post("/api/admin/connections/{code}/test")
def test_system_connection(request: Request, code: str) -> dict:
    actor = admin_user(request)
    try:
        result = build_connection_service().test_connection(code)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    build_app_repository().add_audit_log(actor["username"], "system_connection_tested", f"Kiểm tra kết nối {code}: {result['ok']}")
    notify_if_failed("Lỗi kiểm tra kết nối", result, {"ma_ket_noi": code})
    return result


@router.put("/api/admin/connections/{code}")
def save_system_connection(request: Request, code: str, payload: SystemConnectionPayload) -> dict:
    actor = admin_user(request)
    repository = build_app_repository()
    repository.upsert_system_connection(
        code.strip(),
        payload.name.strip(),
        payload.connection_type.strip(),
        payload.description.strip(),
        payload.config,
        payload.is_active,
    )
    repository.add_audit_log(actor["username"], "system_connection_saved", f"Luu ket noi {code}")
    return {"ok": True}


@router.post("/api/admin/telegram/test-message")
def send_telegram_test_message(request: Request) -> dict:
    actor = admin_user(request)
    result = TelegramNotifier(get_settings()).test()
    build_app_repository().add_audit_log(
        actor["username"],
        "telegram_test_message_sent" if result.get("ok") else "telegram_test_message_failed",
        f"Kiem tra gui tin nhan Telegram: {result.get('message')}",
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message") or "Không gửi được Telegram. Kiểm tra TELEGRAM_TOKEN, MY_TELEGRAM_ID và hãy bấm Start trong bot.",
        )
    return result


@router.get("/api/admin/work-tasks")
def list_work_tasks(request: Request, include_completed: bool = False) -> dict:
    admin_user(request)
    try:
        return {"tasks": build_app_repository().list_work_tasks(include_completed=include_completed)}
    except RuntimeError as error:
        raise_work_task_schema_error(error)


@router.post("/api/admin/work-tasks")
def save_work_task(request: Request, payload: WorkTaskPayload) -> dict:
    actor = admin_user(request)
    task_name = payload.ten_cong_viec.strip()
    if not task_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên công việc không được để trống.")
    if not payload.time or len(payload.time.split(":")) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thời gian chạy chưa đúng định dạng HH:MM.")
    if payload.type == "Once" and not payload.once_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lịch chạy một lần cần nhập ngày chạy.")
    if payload.type == "Weekly" and not payload.weekday:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lịch hàng tuần cần nhập ngày trong tuần.")
    repository = build_app_repository()
    try:
        task_id = payload.task_id.strip() or repository.generate_work_task_id()
    except RuntimeError as error:
        raise_work_task_schema_error(error)
    try:
        repository.save_work_task({
            "task_id": task_id,
            "ten_cong_viec": task_name,
            "type": payload.type,
            "time": payload.time[:5],
            "weekday": payload.weekday.strip(),
            "once_date": payload.once_date.strip(),
            "group": payload.group.strip(),
            "check": payload.check,
        })
    except RuntimeError as error:
        raise_work_task_schema_error(error)
    repository.add_audit_log(actor["username"], "work_task_saved", f"Luu lich cong viec {task_id}")
    return {"ok": True, "task": repository.get_work_task(task_id)}


@router.delete("/api/admin/work-tasks/{task_id}")
def delete_work_task(request: Request, task_id: str) -> dict:
    actor = admin_user(request)
    repository = build_app_repository()
    try:
        if not repository.get_work_task(task_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tác vụ.")
        repository.delete_work_task(task_id)
    except RuntimeError as error:
        raise_work_task_schema_error(error)
    repository.add_audit_log(actor["username"], "work_task_deleted", f"Xoa lich cong viec {task_id}")
    return {"ok": True}


@router.post("/api/admin/work-tasks/{task_id}/complete")
def complete_work_task(request: Request, task_id: str) -> dict:
    actor = admin_user(request)
    repository = build_app_repository()
    try:
        if not repository.get_work_task(task_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tác vụ.")
        repository.complete_work_task(task_id)
    except RuntimeError as error:
        raise_work_task_schema_error(error)
    repository.add_audit_log(actor["username"], "work_task_completed", f"Hoan thanh va an lich cong viec {task_id}")
    return {"ok": True, "message": "Đã đánh dấu hoàn thành và ẩn lịch công việc."}


@router.get("/api/notifications")
def notifications(request: Request) -> dict:
    current_user(request)
    return {
        "notifications": [
            {
                "title": "Thông báo hệ thống",
                "message": "Kênh thông báo nội bộ đã sẵn sàng. Thông báo của quản trị viên sẽ hiển thị tại đây.",
                "created_at": "2026-06-07T00:00:00+07:00",
            }
        ]
    }


@router.get("/api/websites")
def websites(request: Request) -> dict:
    require_feature(request, "vault.view")
    return {"websites": build_app_repository().list_websites(active_only=True)}


@router.get("/api/credentials")
def credentials(request: Request) -> dict:
    user = require_feature(request, "vault.view")
    return {"credentials": build_app_repository().list_credentials(user["id"])}


@router.post("/api/credentials")
def save_credential(request: Request, payload: CredentialPayload) -> dict:
    user = require_feature(request, "vault.manage")
    try:
        build_vault_service().save_credential(
            user, payload.id, payload.website_id, payload.login_username, payload.password, payload.notes
        )
    except (ValueError, sqlite3.IntegrityError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"ok": True}


@router.post("/api/credentials/{credential_id}/reveal")
def reveal_credential(request: Request, credential_id: int) -> dict:
    user = require_feature(request, "vault.reveal")
    try:
        password = build_vault_service().reveal_password(user, credential_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"password": password}


@router.delete("/api/credentials/{credential_id}")
def delete_credential(request: Request, credential_id: int) -> dict:
    user = require_feature(request, "vault.manage")
    try:
        build_vault_service().delete_credential(user, credential_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"ok": True}


@router.get("/api/admin/websites")
def admin_websites(request: Request) -> dict:
    admin_user(request)
    return {"websites": build_app_repository().list_websites()}


@router.post("/api/admin/websites")
def save_admin_website(request: Request, payload: WebsitePayload) -> dict:
    actor = admin_user(request)
    try:
        website = build_vault_service().save_website(
            actor["username"], payload.id, payload.name, payload.url, payload.requires_otp, payload.is_active
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"ok": True, "website": website}



@router.get("/api/admin/features")
def features(request: Request) -> dict:
    admin_user(request)
    return {"features": build_app_repository().list_features()}


@router.put("/api/admin/features/layout")
def save_feature_layout(request: Request, payload: FeatureLayoutPayload) -> dict:
    actor = admin_user(request)
    repository = build_app_repository()
    valid_codes = {feature["code"] for feature in repository.list_features()}
    for item in payload.features:
        if item.code not in valid_codes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Chức năng {item.code} không hợp lệ.")
        if item.parent_code and item.parent_code not in valid_codes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Chức năng cha {item.parent_code} không hợp lệ.")
        try:
            repository.update_feature_layout(item.code, item.name.strip(), item.parent_code, item.sort_order)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    repository.add_audit_log(actor["username"], "feature_layout_saved", f"Cap nhat cau truc menu {len(payload.features)} chuc nang")
    return {"ok": True}


@router.get("/api/admin/roles")
def list_roles(request: Request) -> dict:
    admin_user(request)
    return {"roles": build_app_repository().list_system_roles()}


@router.post("/api/admin/roles")
def save_role(request: Request, payload: SystemRolePayload) -> dict:
    actor = admin_user(request)
    code = payload.code.strip().lower()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã vai trò không được để trống.")
    build_app_repository().save_system_role(
        code,
        payload.name.strip(),
        payload.description.strip(),
        payload.is_active,
        payload.sort_order,
    )
    build_app_repository().add_audit_log(actor["username"], "role_saved", f"Luu vai tro {code}")
    return {"ok": True}


@router.delete("/api/admin/roles/{code}")
def delete_role(request: Request, code: str) -> dict:
    actor = admin_user(request)
    build_app_repository().delete_system_role(code.strip().lower())
    build_app_repository().add_audit_log(actor["username"], "role_deleted", f"Xoa vai tro {code}")
    return {"ok": True}


@router.get("/api/admin/users/{user_id}/permissions")
def user_permissions(request: Request, user_id: int) -> dict:
    admin_user(request)
    return {"feature_codes": build_app_repository().get_user_permissions(user_id)}


@router.put("/api/admin/users/{user_id}/permissions")
def update_permissions(request: Request, user_id: int, payload: PermissionPayload) -> dict:
    actor = admin_user(request)
    valid_codes = {feature["code"] for feature in build_app_repository().list_features()}
    if not set(payload.feature_codes).issubset(valid_codes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Danh sách quyền không hợp lệ.")
    build_app_repository().set_user_permissions(user_id, payload.feature_codes)
    build_app_repository().add_audit_log(actor["username"], "permissions_updated", f"Cập nhật quyền người dùng #{user_id}")
    return {"ok": True}


@router.put("/api/admin/permissions/bulk")
def update_bulk_permissions(request: Request, payload: BulkPermissionPayload) -> dict:
    actor = admin_user(request)
    valid_codes = {feature["code"] for feature in build_app_repository().list_features()}
    if not payload.user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chưa chọn người dùng.")
    if not set(payload.feature_codes).issubset(valid_codes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Danh sách quyền không hợp lệ.")
    build_app_repository().set_bulk_user_permissions(payload.user_ids, payload.feature_codes)
    build_app_repository().add_audit_log(actor["username"], "bulk_permissions_updated", f"Cap quyen cho {len(payload.user_ids)} user")
    return {"ok": True}


@router.get("/api/admin/regions")
def list_regions(request: Request) -> dict:
    admin_user(request)
    return {"regions": build_app_repository().list_data_regions()}


@router.post("/api/admin/regions")
def save_region(request: Request, payload: DataRegionPayload) -> dict:
    actor = admin_user(request)
    build_app_repository().save_data_region(payload.code.strip(), payload.name.strip(), payload.is_active, payload.sort_order)
    build_app_repository().add_audit_log(actor["username"], "region_saved", f"Luu phan vung {payload.code}")
    return {"ok": True}


@router.delete("/api/admin/regions/{code}")
def delete_region(request: Request, code: str) -> dict:
    actor = admin_user(request)
    repository = build_app_repository()
    repository.delete_data_region(code.strip())
    repository.add_audit_log(actor["username"], "region_deleted", f"Xoa phan vung {code}")
    return {"ok": True}


@router.get("/api/admin/users/{user_id}/data-permissions")
def user_data_permissions(request: Request, user_id: int) -> dict:
    admin_user(request)
    return {"region_codes": build_app_repository().get_user_data_permissions(user_id)}


@router.put("/api/admin/data-permissions/bulk")
def update_bulk_data_permissions(request: Request, payload: BulkDataPermissionPayload) -> dict:
    actor = admin_user(request)
    valid_codes = {region["code"] for region in build_app_repository().list_data_regions()}
    if not payload.user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chưa chọn người dùng.")
    if not set(payload.region_codes).issubset(valid_codes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Danh sách phân vùng không hợp lệ.")
    build_app_repository().set_bulk_user_data_permissions(payload.user_ids, payload.region_codes)
    build_app_repository().add_audit_log(actor["username"], "bulk_data_permissions_updated", f"Cap vung du lieu cho {len(payload.user_ids)} user")
    return {"ok": True}
