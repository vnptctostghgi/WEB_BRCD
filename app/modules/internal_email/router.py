from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.data_access.repository_factory import build_repository
from app.modules.internal_email.service import (
    internal_email_status,
    list_internal_email_messages,
    sync_internal_email_once,
    test_internal_email_connection,
)
from app.modules.internal_email.permissions import require_internal_email_permission
from app.settings import get_settings


admin_router = APIRouter(prefix="/api/admin/internal-email", tags=["admin-internal-email"])
ADMIN_EMAIL_LIMIT = 20


def _limit(value: int | str | None = None, default: int = ADMIN_EMAIL_LIMIT) -> int:
    try:
        raw = int(value if value is not None else default)
    except (TypeError, ValueError):
        raw = default
    return min(max(raw, 1), 100)


@admin_router.get("/status")
def admin_internal_email_status(request: Request) -> dict:
    require_internal_email_permission(request, "internal_email.view")
    settings = get_settings()
    return internal_email_status(build_repository(settings), settings)


@admin_router.post("/test")
def admin_internal_email_test(request: Request) -> dict:
    require_internal_email_permission(request, "internal_email.manage")
    settings = get_settings()
    repository = build_repository(settings)
    connection = repository.get_system_connection_by_code("internal_email")
    return test_internal_email_connection(settings, repository, connection)


@admin_router.post("/sync")
def admin_internal_email_sync(request: Request) -> dict:
    actor = require_internal_email_permission(request, "internal_email.manage")
    settings = get_settings()
    repository = build_repository(settings)
    result = sync_internal_email_once(repository, settings)
    try:
        repository.add_audit_log(actor["username"], "internal_email_synced", f"Internal email sync: {result.get('ok')}")
    except Exception:
        pass
    if not result.get("ok"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message") or "Internal email sync failed.")
    return result


@admin_router.get("/messages")
def admin_internal_email_messages(request: Request, limit: int = ADMIN_EMAIL_LIMIT, otp_only: bool = False) -> dict:
    require_internal_email_permission(request, "internal_email.view")
    try:
        messages = list_internal_email_messages(build_repository(get_settings()), limit=_limit(limit), otp_only=otp_only)
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Internal email schema is missing: {str(error)[:200]}") from error
    return {"ok": True, "messages": messages}
