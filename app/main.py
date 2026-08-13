from contextlib import asynccontextmanager
import logging
import mimetypes
import threading
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.application.connection_service import ConnectionService
from app.application.task_scheduler import (
    dashboard_chart_cache_scheduler,
    data_mining_scheduler,
    internal_email_sync_scheduler,
    task_report_auto_scheduler,
    work_task_scheduler,
    zalo_auto_message_scheduler,
)
from app.application.telegram_notifier import TelegramNotifier
from app.data_access.repository_factory import build_repository
from app.modules.internal_email.router import admin_router as internal_email_admin_router
from app.modules.mobile_gateway.router import admin_router as mobile_gateway_admin_router
from app.modules.mobile_gateway.router import router as mobile_gateway_router
from app.modules.public_messages.router import admin_router as public_messages_admin_router
from app.presentation.routes import router as presentation_router
from app.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()
STARTUP_BOOTSTRAP_STATUS_LOCK = threading.Lock()
STARTUP_BOOTSTRAP_STATUS = {
    "status": "pending",
    "started_at": "",
    "finished_at": "",
    "message": "",
}
mimetypes.add_type("image/webp", ".webp")
try:
    settings.validate_for_startup()
except RuntimeError as error:
    if settings.production_strict_startup:
        raise
    logger.warning("Production startup checks need attention: %s", error)
docs_enabled = not settings.is_production
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _set_startup_bootstrap_status(status: str, message: str = "") -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with STARTUP_BOOTSTRAP_STATUS_LOCK:
        STARTUP_BOOTSTRAP_STATUS["status"] = status
        STARTUP_BOOTSTRAP_STATUS["message"] = message
        if status in {"running", "skipped"} and not STARTUP_BOOTSTRAP_STATUS.get("started_at"):
            STARTUP_BOOTSTRAP_STATUS["started_at"] = now
        if status in {"complete", "failed", "skipped"}:
            STARTUP_BOOTSTRAP_STATUS["finished_at"] = now


def _startup_bootstrap_snapshot() -> dict[str, str]:
    with STARTUP_BOOTSTRAP_STATUS_LOCK:
        return dict(STARTUP_BOOTSTRAP_STATUS)


def _bootstrap_repository(repository) -> None:
    _set_startup_bootstrap_status("running", "Repository bootstrap is running.")
    repository.initialize(
        settings.initial_admin_username,
        settings.initial_admin_password.get_secret_value(),
    )
    ConnectionService(repository, settings).seed_current_connections()
    _set_startup_bootstrap_status("complete", "Repository bootstrap complete.")


def _should_background_bootstrap() -> bool:
    return (
        settings.app_database_backend.strip().lower() == "supabase"
        and bool(getattr(settings, "supabase_startup_background_enabled", True))
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository = build_repository(settings)
    schedulers_started = False

    def start_schedulers() -> None:
        nonlocal schedulers_started
        if schedulers_started:
            return
        work_task_scheduler.configure(repository, settings)
        work_task_scheduler.start()
        dashboard_chart_cache_scheduler.configure(repository, settings)
        dashboard_chart_cache_scheduler.start()
        zalo_auto_message_scheduler.configure(repository, settings)
        zalo_auto_message_scheduler.start()
        data_mining_scheduler.configure(repository, settings)
        data_mining_scheduler.start()
        task_report_auto_scheduler.configure(repository, settings)
        task_report_auto_scheduler.start()
        internal_email_sync_scheduler.configure(repository, settings)
        internal_email_sync_scheduler.start()
        schedulers_started = True

    if _should_background_bootstrap():
        def bootstrap_in_background() -> None:
            try:
                _bootstrap_repository(repository)
            except Exception as error:
                logger.exception("Background startup bootstrap failed: %s", error)
                _set_startup_bootstrap_status("failed", str(error))
            finally:
                try:
                    start_schedulers()
                except Exception as error:
                    logger.exception("Cannot start schedulers after bootstrap: %s", error)

        threading.Thread(target=bootstrap_in_background, name="startup-bootstrap", daemon=True).start()
    else:
        _bootstrap_repository(repository)
        start_schedulers()
    try:
        yield
    finally:
        internal_email_sync_scheduler.stop()
        task_report_auto_scheduler.stop()
        data_mining_scheduler.stop()
        zalo_auto_message_scheduler.stop()
        dashboard_chart_cache_scheduler.stop()
        work_task_scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    description="Trang quản trị BRCĐ theo kiến trúc 3 lớp.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret.get_secret_value(),
    session_cookie="brcd_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=settings.is_production,
)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)
app.mount("/static", StaticFiles(directory="app/presentation/static"), name="static")
app.include_router(mobile_gateway_router)
app.include_router(mobile_gateway_admin_router)
app.include_router(internal_email_admin_router)
app.include_router(public_messages_admin_router)


@app.get("/api/ping", include_in_schema=False)
def ping() -> dict:
    return {"ok": True, "status": "alive", "bootstrap": _startup_bootstrap_snapshot()}


app.include_router(presentation_router)


@app.middleware("http")
async def add_response_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") and response.status_code < 400:
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(Exception)
async def notify_unhandled_exception(request: Request, exc: Exception):
    request_id = uuid.uuid4().hex[:12]
    TelegramNotifier(settings).send_message(
        "Web BRCĐ phát sinh lỗi chưa xử lý",
        f"Unhandled application error. Reference: {request_id}",
        {"request_id": request_id, "path": request.url.path, "method": request.method, "type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Hệ thống phát sinh lỗi. Quản trị viên đã được thông báo.", "request_id": request_id},
    )
