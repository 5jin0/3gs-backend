"""Wordbook save button click event log."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class WordbookSaveEvent(Base):
    """Stores each click request for saving a term to wordbook."""

    __tablename__ = "wordbook_save_events"
    __table_args__ = (
        Index("ix_wordbook_save_events_user_created", "user_id", "created_at"),
        Index("ix_wordbook_save_events_user_term", "user_id", "term_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    term_id: Mapped[int] = mapped_column(ForeignKey("terms.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
