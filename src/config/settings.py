"""Application settings for gateway-service."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven gateway configuration."""

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "gateway-service"
    APP_ENV: str = Field(default="development")

    JWT_SECRET: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = "HS256"

    CORE_API_URL: str = "http://core-api-backend:8000"
    INTERVIEW_SERVICE_URL: str = "http://interview-engine-backend:8001"

    HTTP_CLIENT_TIMEOUT: float = 30.0
    HTTP_CLIENT_MAX_CONNECTIONS: int = 100
    HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS: int = 20

    GENERAL_RATE_LIMIT_PER_MINUTE: int = 100
    AUTH_RATE_LIMIT_PER_MINUTE: int = 10

    # ── Cookie settings ───────────────────────────────────────────────────────
    # Set COOKIE_SECURE=true in GCP / any HTTPS environment.
    # Leave false for local Docker dev (no TLS).
    COOKIE_SECURE: bool = False
    COOKIE_SAME_SITE: str = "lax"
    # How long (seconds) each cookie lives in the browser.
    # Access token cookie should match the JWT expiry in core-api.
    COOKIE_ACCESS_MAX_AGE: int = 3600  # 1 hour
    COOKIE_REFRESH_MAX_AGE: int = 604800  # 7 days

    # ── CORS ─────────────────────────────────────────────────────────────────
    # When using credentials (cookies), the browser requires an explicit origin
    # — wildcard "*" is not allowed.  List every frontend origin here.
    # Example: "http://localhost:5173,https://app.ibot.com"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma-separated CORS_ORIGINS string into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()


settings = get_settings()
