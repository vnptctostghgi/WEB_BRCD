from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.data_access.repository_factory import build_repository
from app.modules.internal_email.service import (
    delete_internal_email_otp_rule,
    internal_email_status,
    list_internal_email_messages,
    list_internal_email_otp_rules,
    save_internal_email_otp_rule,
    sync_internal_email_once,
    test_internal_email_connection,
)
from app.modules.internal_email.permissions import require_internal_email_permission
from app.settings import get_settings


admin_router = APIRouter(prefix="/api/admin/internal-email", tags=["admin-internal-email"])
ADMIN_EMAIL_LIMIT = 20


class InternalEmailOtpRulePayload(BaseModel):
    id: str = ""
    sender_pattern: str = Field(min_length=1, max_length=200)
    sender_match_type: Literal["contains", "exact", "equals", "regex"] = "contains"
    label: str = Field(default="", max_length=200)
    direction: Literal["left_to_right", "right_to_left"] = "left_to_right"
    occurrence_index: int = Field(default=1, ge=1, le=200)
    start_position: int = Field(default=1, ge=1, le=500)
    otp_length: int = Field(default=6, ge=1, le=12)
    regex: str = Field(default="", max_length=500)
    priority: int = Field(default=100, ge=0, le=10000)
    enabled: bool = True


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


@admin_router.get("/otp-rules")
def admin_internal_email_otp_rules(request: Request) -> dict:
    require_internal_email_permission(request, "internal_email.view")
    try:
        rules = list_internal_email_otp_rules(build_repository(get_settings()))
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot load internal email OTP rules: {str(error)[:200]}") from error
    return {"ok": True, "rules": rules}


@admin_router.post("/otp-rules")
def admin_save_internal_email_otp_rule(request: Request, payload: InternalEmailOtpRulePayload) -> dict:
    actor = require_internal_email_permission(request, "internal_email.manage")
    repository = build_repository(get_settings())
    try:
        rule = save_internal_email_otp_rule(repository, payload.model_dump(), actor=actor.get("username", ""))
        repository.add_audit_log(actor["username"], "internal_email_otp_rule_saved", f"Internal email OTP rule: {payload.sender_pattern}")
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot save internal email OTP rule: {str(error)[:200]}") from error
    return {"ok": True, "rule": rule}


@admin_router.delete("/otp-rules/{rule_id}")
def admin_delete_internal_email_otp_rule(request: Request, rule_id: str) -> dict:
    actor = require_internal_email_permission(request, "internal_email.manage")
    repository = build_repository(get_settings())
    try:
        delete_internal_email_otp_rule(repository, rule_id)
        repository.add_audit_log(actor["username"], "internal_email_otp_rule_deleted", f"Delete internal email OTP rule {rule_id}")
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot delete internal email OTP rule: {str(error)[:200]}") from error
    return {"ok": True}
