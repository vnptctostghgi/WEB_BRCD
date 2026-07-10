from fastapi import HTTPException, Request, status

from app.presentation.routes import current_user


MOBILE_GATEWAY_FEATURE_CODE = "mobilegateway"

PERMISSIONS = {
    "mobile_gateway.view": "Xem Mobile Gateway",
    "mobile_gateway.manage": "Quan tri Mobile Gateway",
    "mobile_gateway.devices.view": "Xem thiet bi",
    "mobile_gateway.devices.manage": "Quan tri thiet bi",
    "mobile_gateway.sms.view": "Xem SMS",
    "mobile_gateway.sms.view_content": "Xem noi dung SMS",
    "mobile_gateway.notifications.view": "Xem thong bao",
    "mobile_gateway.notifications.view_content": "Xem noi dung thong bao",
    "mobile_gateway.otp.view": "Xem OTP",
    "mobile_gateway.otp.manage": "Quan tri OTP",
    "mobile_gateway.commands.view": "Xem lenh",
    "mobile_gateway.commands.manage": "Gui lenh",
    "mobile_gateway.audit.view": "Xem nhat ky Mobile Gateway",
}


def require_mobile_permission(request: Request, permission: str) -> dict:
    user = current_user(request)
    if user.get("role") == "admin":
        return user
    granted = set(user.get("permissions") or [])
    if permission not in granted and "mobile_gateway.manage" not in granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ban chua duoc cap quyen Mobile Gateway.",
        )
    return user


def has_mobile_permission(user: dict, permission: str) -> bool:
    if user.get("role") == "admin":
        return True
    granted = set(user.get("permissions") or [])
    return permission in granted or "mobile_gateway.manage" in granted
