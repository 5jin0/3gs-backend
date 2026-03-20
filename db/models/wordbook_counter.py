"""Per-user counters for wordbook usage metrics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class WordbookCounter(Base):
    """Aggregated wordbook counters per user."""

    __tablename__ = "wordbook_counters"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    save_click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    save_success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    wordbook_view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
