from __future__ import annotations

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ADMIN_PASSWORD_HASH = (
    "$2b$12$sdOU8uwfeIt/6CaZUIM6ke71zg30wHn0r3QC4TDA3xHYwQxTVEEXi"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        case_sensitive=False,
    )

    env: str = Field(default="development")
    debug: bool = Field(default=False)
    docs_enabled: bool = Field(default=True)

    secret_key: str = Field(min_length=32)
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1, le=60 * 24 * 30)

    admin_username: str = Field(default="admin", min_length=3, max_length=64)
    admin_password_hash: str = Field(default=DEFAULT_ADMIN_PASSWORD_HASH, min_length=10)

    cors_origins: list[str] = Field(default_factory=list)
    trusted_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    session_cookie: str = Field(default="influx_demo_session", min_length=1, max_length=64)
    session_max_age_seconds: int = Field(default=60 * 60 * 8, ge=60, le=60 * 60 * 24 * 30)

    influx_url: AnyHttpUrl = Field(default="http://influxdb:8086")
    influx_token: str = Field(min_length=10)
    influx_org: str = Field(min_length=1)
    influx_bucket: str = Field(min_length=1)
    influx_measurement: str = Field(default="device_metrics")
    influx_timeout_ms: int = Field(default=10_000, ge=1000, le=120_000)

    weather_user_agent: str = Field(
        default="influx-db-demo/0.1 (contact: you@example.com)",
        min_length=3,
        max_length=256,
    )
    weather_timeout_seconds: float = Field(default=10.0, ge=1.0, le=30.0)
    weather_measurement: str = Field(default="norwegian_weather", min_length=1, max_length=64)
    weather_fetch_on_login: bool = Field(default=True)
    weather_min_refresh_interval_seconds: int = Field(default=300, ge=0, le=3600)
    weather_background_refresh_enabled: bool = Field(default=True)
    weather_background_refresh_interval_seconds: float = Field(default=1.0, ge=0.25, le=3600.0)

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


def load_settings() -> Settings:
    settings = Settings()
    if not settings.cors_origins:
        settings.cors_origins = ["http://localhost:3000", "http://localhost:8000"]
    return settings
