#!/usr/bin/env python3
"""Backfill search lifecycle events into `search_events`.

Purpose:
- Older code stored `search_complete`/`search_exit` only in
  `search_analytics_events`.
- Admin UX metrics aggregate those event types from `search_events`.

This script copies missing lifecycle rows from `search_analytics_events`
to `search_events` in an idempotent way.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from db.base import Base
    from db.models.search_analytics_event import SearchAnalyticsEvent
    from db.models.search_event import SearchEvent
    from db.session import SessionLocal, engine

    Base.metadata.create_all(
        bind=engine,
        tables=[SearchAnalyticsEvent.__table__, SearchEvent.__table__],
    )

    db = SessionLocal()
    try:
        before = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM search_analytics_events a
                    WHERE a.event_type IN ('search_complete', 'search_exit')
                    """
                )
            ).scalar_one()
            or 0
        )

        inserted = int(
            db.execute(
                text(
                    """
                    INSERT INTO search_events (user_id, event_type, keyword, created_at)
                    SELECT a.user_id, a.event_type, a.keyword, a.created_at
                    FROM search_analytics_events a
                    WHERE a.event_type IN ('search_complete', 'search_exit')
                      AND NOT EXISTS (
                          SELECT 1
                          FROM search_events s
                          WHERE s.user_id = a.user_id
                            AND s.event_type = a.event_type
                            AND s.keyword = a.keyword
                            AND s.created_at = a.created_at
                      )
                    """
                )
            ).rowcount
            or 0
        )
        db.commit()

        search_events_lifecycle = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM search_events
                    WHERE event_type IN ('search_complete', 'search_exit')
                    """
                )
            ).scalar_one()
            or 0
        )

        print(
            "[backfill] source_lifecycle_rows="
            f"{before} inserted={inserted} target_lifecycle_rows={search_events_lifecycle}",
            flush=True,
        )
        return 0
    except SQLAlchemyError as e:
        db.rollback()
        print(f"[backfill] ERROR {e}", file=sys.stderr, flush=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

