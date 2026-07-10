class MobileGatewayError(Exception):
    """Base error for Mobile Gateway workflows."""


class PairingError(MobileGatewayError):
    """Raised when a pairing request cannot be completed."""


class DeviceAuthError(MobileGatewayError):
    """Raised when a device HMAC request is not valid."""


class OtpServiceError(MobileGatewayError):
    """Raised when OTP service input is invalid."""
