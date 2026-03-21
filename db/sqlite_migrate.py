"""SQLite 전용: 기존 DB 파일에 모델에만 추가된 컬럼을 보강합니다.

`Base.metadata.create_all()`은 기존 테이블을 ALTER 하지 않으므로,
로컬 `pangyopass.db`가 옛 스키마일 때 ORM과 불일치로 실패하는 것을 막습니다.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def patch_sqlite_schema(engine: Engine) -> None:
    """SQLite DB에 누락된 컬럼을 추가합니다 (멱등)."""

    if engine.dialect.name != "sqlite":
        return

    insp = inspect(engine)

    # users.is_admin (관리자 플래그)
    if insp.has_table("users"):
        columns = {c["name"] for c in insp.get_columns("users")}
        if "is_admin" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
                    )
                )
            logger.info(
                "sqlite_migrate: added users.is_admin (existing DB patched)"
            )
