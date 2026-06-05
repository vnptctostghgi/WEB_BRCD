from pathlib import Path
import sqlite3
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.application.auth_service import AuthService
from app.application.database_service import DatabaseService
from app.application.vault_service import VaultService
from app.application.connection_service import ConnectionService
from app.application.telegram_notifier import TelegramNotifier
from app.data_access.app_repository import AppRepository
from app.data_access.repository_factory import build_repository
from app.data_access.oracle_repository import OracleRepository
from app.settings import get_settings


router = APIRouter()
templates = Jinja2Templates(directory=Path("app/presentation/templates"))


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


def notify_login_failed_threshold(request: Request, username: str) -> None:
    repository = build_app_repository()
    normalized_username = username.strip() or "unknown"
    failures = 0
    for log in repository.list_audit_logs(limit=50):
        if log.get("actor") != normalized_username:
            continue
        if log.get("action") == "login_success":
            break
        if log.get("action") == "login_failed":
            failures += 1
    if failures and failures % 5 == 0:
        client_host = request.client.host if request.client else "unknown"
        TelegramNotifier(get_settings()).send_message(
            "Cảnh báo đăng nhập sai",
            f"Tài khoản {normalized_username} đã đăng nhập sai {failures} lần liên tiếp.",
            {"ip": client_host, "nguong_canh_bao": 5},
        )


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
