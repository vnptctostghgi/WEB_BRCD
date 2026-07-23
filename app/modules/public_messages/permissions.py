from fastapi import HTTPException, Request, status

from app.presentation.routes import current_user


PUBLIC_MESSAGES_FEATURE_CODE = "publicmessages"

PERMISSIONS = {
    "public_messages.view": "Xem n\u1ed9i dung public",
    "public_messages.manage": "Qu\u1ea3n tr\u1ecb n\u1ed9i dung public",
}


def require_public_messages_permission(request: Request, permission: str) -> dict:
    user = current_user(request)
    if user.get("role") == "admin":
        return user
    granted = set(user.get("permissions") or [])
    if permission not in granted and "public_messages.manage" not in granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="B\u1ea1n ch\u01b0a \u0111\u01b0\u1ee3c c\u1ea5p quy\u1ec1n n\u1ed9i dung public.",
        )
    return user


def has_public_messages_permission(user: dict, permission: str) -> bool:
    if user.get("role") == "admin":
        return True
    granted = set(user.get("permissions") or [])
    return permission in granted or "public_messages.manage" in granted
