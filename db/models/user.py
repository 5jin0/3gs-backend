"""User ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.saved_term import SavedTerm


class User(Base):
    """Application user.

    This model is intentionally minimal for early auth flows and can be extended
    later with profile/role/status fields.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    saved_terms: Mapped[list["SavedTerm"]] = relationship(
        "SavedTerm",
        back_populates="user",
        cascade="all, delete-orphan",
    )

