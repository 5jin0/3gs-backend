"""관리자 대시보드용 메트릭 집계."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.repeat_search_log import RepeatSearchLog
from db.models.saved_term import SavedTerm
from db.models.search_analytics_event import SearchAnalyticsEvent
from db.models.search_event import SearchEvent
from db.models.term import Term
from db.models.user import User
from db.models.user_access_event import UserAccessEvent
from db.models.wordbook_counter import WordbookCounter
from db.models.wordbook_save_event import WordbookSaveEvent
from schemas.admin import AdminMetricsOverview, AdminRecentBlock, AdminTotalsBlock


def _count(db: Session, model: type, *where_clauses) -> int:
    stmt = select(func.count()).select_from(model)
    for clause in where_clauses:
        stmt = stmt.where(clause)
    return int(db.scalar(stmt) or 0)


def _sum_int(db: Session, column) -> int:
    value = db.scalar(select(func.coalesce(func.sum(column), 0)))
    return int(value or 0)


def build_admin_metrics_overview(db: Session, *, recent_days: int) -> AdminMetricsOverview:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=recent_days)

    totals = AdminTotalsBlock(
        users=_count(db, User),
        terms=_count(db, Term),
        saved_terms=_count(db, SavedTerm),
        repeat_search_log_rows=_count(db, RepeatSearchLog),
        user_access_events=_count(db, UserAccessEvent),
        user_access_login_success=_count(
            db, UserAccessEvent, UserAccessEvent.event_type == "login_success"
        ),
        user_access_wordbook_view=_count(
            db, UserAccessEvent, UserAccessEvent.event_type == "wordbook_view"
        ),
        search_events=_count(db, SearchEvent),
        search_analytics_events=_count(db, SearchAnalyticsEvent),
        wordbook_save_events=_count(db, WordbookSaveEvent),
        wordbook_counter_save_click_sum=_sum_int(db, WordbookCounter.save_click_count),
        wordbook_counter_save_success_sum=_sum_int(db, WordbookCounter.save_success_count),
        wordbook_counter_wordbook_view_sum=_sum_int(db, WordbookCounter.wordbook_view_count),
    )

    recent = AdminRecentBlock(
        new_users=_count(db, User, User.created_at >= cutoff),
        new_terms=_count(db, Term, Term.created_at >= cutoff),
        new_saved_terms=_count(db, SavedTerm, SavedTerm.created_at >= cutoff),
        user_access_events=_count(db, UserAccessEvent, UserAccessEvent.created_at >= cutoff),
        user_access_login_success=_count(
            db,
            UserAccessEvent,
            UserAccessEvent.event_type == "login_success",
            UserAccessEvent.created_at >= cutoff,
        ),
        user_access_wordbook_view=_count(
            db,
            UserAccessEvent,
            UserAccessEvent.event_type == "wordbook_view",
            UserAccessEvent.created_at >= cutoff,
        ),
        search_events=_count(db, SearchEvent, SearchEvent.created_at >= cutoff),
        search_analytics_events=_count(
            db, SearchAnalyticsEvent, SearchAnalyticsEvent.created_at >= cutoff
        ),
        wordbook_save_events=_count(
            db, WordbookSaveEvent, WordbookSaveEvent.created_at >= cutoff
        ),
    )

    return AdminMetricsOverview(
        generated_at_utc=now,
        recent_days=recent_days,
        recent_cutoff_utc=cutoff,
        totals=totals,
        recent=recent,
    )
