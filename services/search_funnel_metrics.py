"""검색 퍼널·비율 집계 (search_events).

지표 정의는 schemas.admin.SearchFunnelMetrics 의 필드 description 과 동일하게 유지합니다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.search_event import SearchEvent
from schemas.admin import SearchFunnelDistinctUsers, SearchFunnelEventCounts, SearchFunnelMetrics, SearchFunnelRates

KNOWN_TYPES = frozenset(
    {
        "search_start",
        "search_click",
        "suggestion_select",
        "search_complete",
        "search_exit",
    }
)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_time_range(
    start: datetime | None,
    end: datetime | None,
) -> tuple[datetime, datetime]:
    """기본: end=지금, start=end-7일. 모두 UTC로 정규화."""

    now = datetime.now(timezone.utc)
    end_ = _ensure_utc(end) if end is not None else now
    start_ = _ensure_utc(start) if start is not None else end_ - timedelta(days=7)
    if start_ > end_:
        raise ValueError("start must be on or before end")
    return start_, end_


def build_search_funnel_metrics(
    db: Session,
    *,
    start: datetime | None,
    end: datetime | None,
) -> SearchFunnelMetrics:
    start_utc, end_utc = resolve_time_range(start, end)

    rows = db.execute(
        select(SearchEvent.event_type, func.count())
        .where(
            SearchEvent.created_at >= start_utc,
            SearchEvent.created_at <= end_utc,
        )
        .group_by(SearchEvent.event_type)
    ).all()

    raw: dict[str, int] = {str(r[0]): int(r[1]) for r in rows}
    other = sum(c for t, c in raw.items() if t not in KNOWN_TYPES)

    def _c(name: str) -> int:
        return int(raw.get(name, 0))

    c_start = _c("search_start")
    c_click = _c("search_click")
    c_sug = _c("suggestion_select")
    c_complete = _c("search_complete")
    c_exit = _c("search_exit")
    total = sum(raw.values())

    unique_any = int(
        db.scalar(
            select(func.count(func.distinct(SearchEvent.user_id))).where(
                SearchEvent.created_at >= start_utc,
                SearchEvent.created_at <= end_utc,
            )
        )
        or 0
    )
    unique_start = int(
        db.scalar(
            select(func.count(func.distinct(SearchEvent.user_id))).where(
                SearchEvent.event_type == "search_start",
                SearchEvent.created_at >= start_utc,
                SearchEvent.created_at <= end_utc,
            )
        )
        or 0
    )

    distinct_users = SearchFunnelDistinctUsers(
        unique_users_with_any_event=unique_any,
        unique_users_with_search_start=unique_start,
    )

    counts = SearchFunnelEventCounts(
        search_start=c_start,
        search_click=c_click,
        suggestion_select=c_sug,
        search_complete=c_complete,
        search_exit=c_exit,
        other=other,
        total_events=total,
    )

    def _ratio(num: int, den: int) -> float | None:
        if den <= 0:
            return None
        return round(num / den, 6)

    # 검색 시작률: 기간 내 검색 이벤트가 1건 이상인 유저 중, search_start 를 1회 이상 낸 유저 비율
    search_start_rate = _ratio(unique_start, unique_any)

    # 검색 클릭률: 이벤트 건수 기준 search_click / search_start
    search_click_rate = _ratio(c_click, c_start)

    # 자동완성 제안 클릭률: suggestion_select / search_start (시작 대비 제안 선택)
    suggestion_select_rate = _ratio(c_sug, c_start)

    # 검색 완료율: search_complete / search_start
    search_complete_rate = _ratio(c_complete, c_start)

    # 검색 실패율: 1 - (search_complete / search_start)  (시작 대비 미완료 비율)
    search_failure_rate: float | None = None
    if c_start > 0:
        search_failure_rate = round(1.0 - (c_complete / c_start), 6)

    # 부가: 전체 추적 이벤트 중 search_start 비중
    search_start_share_of_events = _ratio(c_start, total)

    rates = SearchFunnelRates(
        search_start_rate=search_start_rate,
        search_start_share_of_tracked_events=search_start_share_of_events,
        search_click_rate=search_click_rate,
        suggestion_select_rate=suggestion_select_rate,
        search_complete_rate=search_complete_rate,
        search_failure_rate=search_failure_rate,
    )

    return SearchFunnelMetrics(
        range_start_utc=start_utc,
        range_end_utc=end_utc,
        source_table="search_events",
        counts=counts,
        distinct_users=distinct_users,
        rates=rates,
    )
