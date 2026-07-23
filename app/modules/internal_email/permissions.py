from fastapi import HTTPException, Request, status

from app.presentation.routes import current_user


INTERNAL_EMAIL_FEATURE_CODE = "internalemail"

PERMISSIONS = {
    "internal_email.view": "Xem Mail noi bo",
    "internal_email.manage": "Quan tri Mail noi bo",
}


def require_internal_email_permission(request: Request, permission: str) -> dict:
    user = current_user(request)
    if user.get("role") == "admin":
        return user
    granted = set(user.get("permissions") or [])
    if permission not in granted and "internal_email.manage" not in granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ban chua duoc cap quyen Mail noi bo.",
        )
    return user


def has_internal_email_permission(user: dict, permission: str) -> bool:
    if user.get("role") == "admin":
        return True
    granted = set(user.get("permissions") or [])
    return permission in granted or "internal_email.manage" in granted
