"""Saved term (user wordbook) ORM model.

Stores which ``Term`` rows each ``User`` has bookmarked. SQLite-compatible.
Duplicate saves are prevented by a composite unique key on (user_id, term_id).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.term import Term
    from db.models.user import User


class SavedTerm(Base):
    """User ↔ Term save / wordbook row (one row per user+term pair).

    Intended for endpoints such as ``POST /terms/save`` and ``GET /terms/saved``.
    """

    __tablename__ = "saved_terms"
    __table_args__ = (
        UniqueConstraint("user_id", "term_id", name="uq_saved_terms_user_term"),
        # Speed up: list saves for a user ordered by created_at (common list query).
        Index("ix_saved_terms_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term_id: Mapped[int] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="saved_terms")
    term: Mapped["Term"] = relationship("Term", back_populates="saved_terms")

