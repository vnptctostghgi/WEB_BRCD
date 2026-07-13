from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


_PLACEHOLDER_SESSION_SECRETS = {
    "",
    "change-this-session-secret",
    "hay-thay-bang-chuoi-bi-mat-dai-va-ngau-nhien",
}
_PLACEHOLDER_ADMIN_PASSWORDS = {
    "",
    "ChangeMe123!",
    "Admin@Brcd2026!",
    "admin",
    "password",
}


def _secret_text(secret: SecretStr) -> str:
    return secret.get_secret_value().strip()


class Settings(BaseSettings):
    app_name: str = "Hệ thống quản trị đặc biệt"
    app_env: str = "development"
    app_database_backend: str = "sqlite"
    app_database_path: str = "data/app.db"
    session_secret: SecretStr = Field(default=SecretStr("change-this-session-secret"))
    initial_admin_username: str = "admin"
    initial_admin_password: SecretStr = Field(default=SecretStr("ChangeMe123!"))

    internal_api_url: str = "http://10.92.17.88:8000/api/du-lieu-web"
    internal_api_mock_mode: bool = True
    internal_api_timeout_seconds: int = 20
    internal_api_token: SecretStr = Field(default=SecretStr(""))
    dynamic_report_fetch_page_size: int = 500
    dynamic_report_export_max_rows: int = 100000
    dashboard_tab_max_workers: int = 10
    dashboard_chart_cache_enabled: bool = True
    dashboard_chart_cache_report_ids: str = "*"
    dashboard_chart_cache_report_codes: str = "*"
    dashboard_chart_cache_ttl_seconds: int = 300
    dashboard_chart_cache_auto_refresh_enabled: bool = False
    dashboard_chart_cache_refresh_interval_seconds: int = 300
    app_public_url: str = ""

    supabase_rest_url: str = ""
    supabase_publishable_key: SecretStr = Field(default=SecretStr(""))
    supabase_secret_key: SecretStr = Field(default=SecretStr(""))

    telegram_token: SecretStr = Field(default=SecretStr(""))
    bot_token: SecretStr = Field(default=SecretStr(""))
    my_telegram_id: int = 0
    bot_username: str = ""
    zalo_bot_token: SecretStr = Field(default=SecretStr(""))
    zalo_webhook_url: str = ""
    zalo_webhook_secret: SecretStr = Field(default=SecretStr(""))
    zalo_auto_reply_enabled: bool = True
    onebss_login_url: str = "https://onebss.vnpt.vn/"
    onebss_username: str = ""
    onebss_password: SecretStr = Field(default=SecretStr(""))
    onebss_download_timeout_seconds: int = 180
    data_mining_download_dir: str = "data/data_mining_downloads"
    google_drive_service_account_json_base64: SecretStr = Field(default=SecretStr(""))
    google_drive_service_account_json: SecretStr = Field(default=SecretStr(""))
    google_drive_service_account_file: str = ""
    google_drive_folder_id: str = ""
    google_drive_impersonated_user: str = ""
    google_drive_oauth_client_id: str = ""
    google_drive_oauth_client_secret: SecretStr = Field(default=SecretStr(""))
    google_drive_oauth_redirect_uri: str = ""
    production_strict_startup: bool = False
    mobile_gateway_enabled: bool = True
    mobile_gateway_master_key: SecretStr = Field(default=SecretStr(""))
    otp_encryption_key: SecretStr = Field(default=SecretStr(""))
    mobile_gateway_pairing_ttl_seconds: int = 0
    mobile_gateway_hmac_max_clock_skew_seconds: int = 300
    mobile_gateway_online_threshold_seconds: int = 180

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def validate_for_startup(self) -> None:
        if not self.is_production:
            return

        errors: list[str] = []
        session_secret = _secret_text(self.session_secret)
        if len(session_secret) < 32 or session_secret in _PLACEHOLDER_SESSION_SECRETS:
            errors.append("SESSION_SECRET must be a random value with at least 32 characters")

        initial_admin_password = _secret_text(self.initial_admin_password)
        if len(initial_admin_password) < 12 or initial_admin_password in _PLACEHOLDER_ADMIN_PASSWORDS:
            errors.append("INITIAL_ADMIN_PASSWORD must not use a default or weak value")

        backend = self.app_database_backend.strip().lower()
        if backend not in {"sqlite", "supabase"}:
            errors.append("APP_DATABASE_BACKEND must be sqlite or supabase")
        if backend == "supabase":
            if not self.supabase_rest_url.strip():
                errors.append("SUPABASE_REST_URL is required when APP_DATABASE_BACKEND=supabase")
            if not _secret_text(self.supabase_secret_key):
                errors.append("SUPABASE_SECRET_KEY is required when APP_DATABASE_BACKEND=supabase")

        if self.internal_api_mock_mode:
            errors.append("INTERNAL_API_MOCK_MODE must be false in production")
        if not self.internal_api_url.strip():
            errors.append("INTERNAL_API_URL is required in production")

        if self.google_drive_oauth_client_id.strip() and not _secret_text(self.google_drive_oauth_client_secret):
            errors.append("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET is required with GOOGLE_DRIVE_OAUTH_CLIENT_ID")

        if (_secret_text(self.zalo_bot_token) or self.zalo_webhook_url.strip()) and not _secret_text(self.zalo_webhook_secret):
            errors.append("ZALO_WEBHOOK_SECRET is required when Zalo webhook is enabled")

        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
