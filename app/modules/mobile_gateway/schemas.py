from typing import Any, Literal

from pydantic import BaseModel, Field


class PairDevicePayload(BaseModel):
    pairing_code: str
    device_name: str = ""
    platform: str = "android"
    manufacturer: str = ""
    model: str = ""
    android_version: str = ""
    app_version: str = ""


class SmsMessageIn(BaseModel):
    external_id: str
    sender: str
    body: str
    received_at: str
    subscription_id: str = ""
    sim_slot: int | None = None


class SmsBatchPayload(BaseModel):
    messages: list[SmsMessageIn] = Field(default_factory=list)


class NotificationIn(BaseModel):
    external_id: str
    package_name: str
    app_name: str = ""
    title: str = ""
    text: str = ""
    posted_at: str


class NotificationBatchPayload(BaseModel):
    notifications: list[NotificationIn] = Field(default_factory=list)


class HeartbeatPayload(BaseModel):
    app_version: str = ""
    android_version: str = ""
    manufacturer: str = ""
    model: str = ""
    battery_percent: int | None = None
    charging: bool = False
    network_type: str = ""
    pending_sms: int = 0
    pending_notifications: int = 0
    sms_permission: bool = False
    notification_access: bool = False
    battery_optimization_ignored: bool = False
    last_sms_received_at: str | None = None


class CommandResultPayload(BaseModel):
    status: Literal["acknowledged", "completed", "failed"] = "completed"
    result: dict[str, Any] = Field(default_factory=dict)
    sanitized_error: str = ""


class DiagnosticsPayload(BaseModel):
    app_version: str = ""
    android_version: str = ""
    manufacturer: str = ""
    model: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    sanitized_error: str = ""


class ClipboardPayload(BaseModel):
    text: str = ""
    captured_at: str = ""


class DeviceUpdatePayload(BaseModel):
    name: str = ""


class DevicePolicyPayload(BaseModel):
    sms_enabled: bool = True
    notifications_enabled: bool = False
    clipboard_enabled: bool = False
    diagnostics_enabled: bool = True
    notification_allowlist: list[str] = Field(default_factory=list)
    heartbeat_interval_minutes: int = 15
    sync_interval_minutes: int = 15
    batch_size: int = 50
    local_retention_days: int = 14
    minimum_app_version: str = "1.1.0"
    force_update: bool = False


class AdminCommandPayload(BaseModel):
    command_type: Literal[
        "sync_sms",
        "sync_notifications",
        "refresh_status",
        "refresh_policy",
        "upload_diagnostics",
        "clear_synced_local_queue",
    ]
    device_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int = 3600


class OtpConfigurationPayload(BaseModel):
    id: int | None = None
    service_code: str
    service_name: str
    enabled: bool = True
    source_type: Literal["sms", "notification", "both"] = "sms"
    sender_pattern: str = ""
    sender_match_type: Literal["contains", "equals", "regex"] = "contains"
    package_pattern: str = ""
    title_pattern: str = ""
    otp_regex: str = r"(?<!\d)(\d{4,8})(?!\d)"
    otp_keyword: str = ""
    otp_length_min: int = 4
    otp_length_max: int = 8
    wait_timeout_seconds: int = 120
    validity_seconds: int = 180
    device_id: str = ""
    sim_slot: int | None = None
    auto_fill_enabled: bool = True
    manual_fallback_enabled: bool = True
    priority: int = 100


class OtpRegexTestPayload(BaseModel):
    otp_regex: str
    sample_text: str


class OtpRequestCreatePayload(BaseModel):
    service_code: str
    job_id: str = ""
    timeout_seconds: int | None = None
