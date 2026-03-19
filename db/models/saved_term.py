"""Saved term (bookmark) ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SavedTerm(Base):
    """User-saved term mapping.

    This model is designed for endpoints like:
    - POST /terms/save
    - GET /terms/saved
    """

    __tablename__ = "saved_terms"
    __table_args__ = (
        UniqueConstraint("user_id", "term_id", name="uq_saved_terms_user_term"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("terms.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

