"""Search analytics event model (with cohort tagging)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SearchAnalyticsEvent(Base):
    """Stores search lifecycle events with user cohort information."""

    __tablename__ = "search_analytics_events"
    __table_args__ = (
        Index("ix_search_analytics_user_created", "user_id", "created_at"),
        Index("ix_search_analytics_type_cohort", "event_type", "cohort"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    cohort: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
