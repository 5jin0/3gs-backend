"""Environment-based application settings.

We keep configuration in one place so local/dev/prod can share the same code
while swapping values via environment variables.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PP_",
        case_sensitive=False,
        extra="ignore",
    )

    # Base
    app_name: str = "PangyoPass API"
    environment: str = "local"  # local/dev/staging/prod, etc.

    # CORS
    # Example: PP_CORS_ORIGINS='["http://localhost:3000","https://pangyopass.com"]'
    cors_origins: List[str] = ["http://localhost:3000"]

    # Database
    # SQLite default for local development.
    # Change via env: PP_DATABASE_URL=postgresql+psycopg://...
    database_url: str = "sqlite:///./pangyopass.db"
    db_echo: bool = False

    # Security placeholders (used in later steps)
    secret_key: str = "CHANGE_ME"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Next.js 관리자 분석 API 접두 (프론트 NEXT_PUBLIC_ADMIN_ANALYTICS_PREFIX 와 맞출 것)
    # 예: PP_ADMIN_ANALYTICS_PREFIX=/admin/analytics
    admin_analytics_prefix: str = "/admin/analytics"


@lru_cache
def get_settings() -> Settings:
    """Cached settings getter to avoid re-parsing env per request."""

    return Settings()

