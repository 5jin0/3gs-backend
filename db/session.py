"""Database engine and session configuration.

Designed for easy migration from SQLite(local) to Postgres(prod) via env vars.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    future=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a DB session per request."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

