from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
