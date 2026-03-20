"""Repeated search counter without timestamp field."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class RepeatSearchLog(Base):
    """Tracks how many times a user searched the same keyword."""

    __tablename__ = "repeat_search_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_repeat_search_user_keyword"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
