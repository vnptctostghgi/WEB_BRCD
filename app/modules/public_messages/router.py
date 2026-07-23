from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.data_access.repository_factory import build_repository
from app.modules.public_messages.permissions import require_public_messages_permission
from app.modules.public_messages.repository import PublicMessagesRepository
from app.settings import get_settings


admin_router = APIRouter(prefix="/api/admin/public-messages", tags=["admin-public-messages"])
ADMIN_PUBLIC_MESSAGE_LIMIT = 80


class PublicSenderRulePayload(BaseModel):
    source_type: Literal["email", "sms"]
    sender_pattern: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=200)
    is_active: bool = True


def _repository() -> PublicMessagesRepository:
    settings = get_settings()
    return PublicMessagesRepository(build_repository(settings), settings)


def _limit(value: int | str | None = None, default: int = ADMIN_PUBLIC_MESSAGE_LIMIT) -> int:
    try:
        raw = int(value if value is not None else default)
    except (TypeError, ValueError):
        raw = default
    return min(max(raw, 1), 200)


@admin_router.get("/feed")
def admin_public_message_feed(request: Request, limit: int = ADMIN_PUBLIC_MESSAGE_LIMIT) -> dict:
    require_public_messages_permission(request, "public_messages.view")
    try:
        items = _repository().list_public_messages(limit=_limit(limit))
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Public message schema is missing: {str(error)[:200]}") from error
    return {"ok": True, "items": items}


@admin_router.get("/rules")
def admin_public_message_rules(request: Request, source_type: str = "") -> dict:
    require_public_messages_permission(request, "public_messages.view")
    try:
        rules = _repository().list_rules(source_type=source_type)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Public message schema is missing: {str(error)[:200]}") from error
    return {"ok": True, "rules": rules}


@admin_router.post("/rules")
def admin_save_public_message_rule(request: Request, payload: PublicSenderRulePayload) -> dict:
    actor = require_public_messages_permission(request, "public_messages.manage")
    repository = _repository()
    try:
        rule = repository.save_rule(
            source_type=payload.source_type,
            sender_pattern=payload.sender_pattern,
            label=payload.label,
            is_active=payload.is_active,
            actor=actor.get("username", ""),
        )
        repository.base.add_audit_log(
            actor["username"],
            "public_message_rule_saved",
            f"Public {payload.source_type}: {payload.sender_pattern}",
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Public message schema is missing: {str(error)[:200]}") from error
    return {"ok": True, "rule": rule}


@admin_router.delete("/rules/{rule_id}")
def admin_delete_public_message_rule(request: Request, rule_id: str) -> dict:
    actor = require_public_messages_permission(request, "public_messages.manage")
    repository = _repository()
    try:
        repository.delete_rule(rule_id)
        repository.base.add_audit_log(actor["username"], "public_message_rule_deleted", f"Delete public rule {rule_id}")
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Public message schema is missing: {str(error)[:200]}") from error
    return {"ok": True}
