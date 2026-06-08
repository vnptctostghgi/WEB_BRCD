from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.data_access.repository_factory import build_repository
from app.application.connection_service import ConnectionService
from app.application.openvpn_service import openvpn_service
from app.application.oracle_pool import oracle_pool_service
from app.application.task_scheduler import work_task_scheduler
from app.application.telegram_notifier import TelegramNotifier
from app.presentation.routes import router
from app.settings import get_settings


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository = build_repository(settings)
    repository.initialize(
        settings.initial_admin_username,
        settings.initial_admin_password.get_secret_value(),
    )
    ConnectionService(repository, settings).seed_current_connections()
    openvpn_service.configure(settings)
    oracle_pool_service.configure(settings)
    work_task_scheduler.configure(repository, settings)
    openvpn_service.start()
    oracle_pool_service.start()
    work_task_scheduler.start()
    try:
        yield
    finally:
        work_task_scheduler.stop()
        oracle_pool_service.stop()
        openvpn_service.stop()


app = FastAPI(
    title=settings.app_name,
    description="Trang quan tri BRCĐ theo kien truc 3 lop.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret.get_secret_value(),
    session_cookie="brcd_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=settings.app_env == "production",
)
app.mount("/static", StaticFiles(directory="app/presentation/static"), name="static")
app.include_router(router)


@app.exception_handler(Exception)
async def notify_unhandled_exception(request: Request, exc: Exception):
    TelegramNotifier(settings).send_message(
        "Web BRCĐ phát sinh lỗi chưa xử lý",
        str(exc),
        {"path": request.url.path, "method": request.method, "type": type(exc).__name__},
    )
    return JSONResponse(status_code=500, content={"detail": "Hệ thống phát sinh lỗi. Quản trị viên đã được thông báo."})
