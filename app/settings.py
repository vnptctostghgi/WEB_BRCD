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

    db_mock_mode: bool = True
    db_host: str = ""
    db_port: int = 1521
    db_service: str = ""
    db_user: str = ""
    db_pass: SecretStr = Field(default=SecretStr(""))

    supabase_rest_url: str = ""
    supabase_publishable_key: SecretStr = Field(default=SecretStr(""))
    supabase_secret_key: SecretStr = Field(default=SecretStr(""))

    telegram_token: SecretStr = Field(default=SecretStr(""))
    bot_token: SecretStr = Field(default=SecretStr(""))
    my_telegram_id: int = 0
    bot_username: str = ""

    vpn_host: str = ""
    vpn_port: int = 4443
    vpn_username: str = ""
    vpn_password: SecretStr = Field(default=SecretStr(""))
    vpn_type: str = "ssl"
    ssl_vpn_binary: str = "openconnect"
    ssl_vpn_protocol: str = "fortinet"
    ssl_vpn_restart_seconds: int = 10
    vpn_tls_verify: bool = False
    vpn_test_targets: str = ""

    oracle_pool_min: int = 5
    oracle_pool_max: int = 30
    oracle_pool_increment: int = 1
    oracle_connect_timeout_ms: int = 10000
    oracle_query_timeout_ms: int = 5000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
