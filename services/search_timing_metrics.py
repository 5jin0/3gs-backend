"""검색 이벤트 간 시간차·이탈(인지부담) 집계 (search_events).

세션: 동일 user_id + keyword 이며, 시간순으로 연속된 이벤트 간격이
`session_gap_seconds` 를 초과하면 새 세션으로 분리합니다.
"""

from __future__ import annotations

import math
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.search_event import SearchEvent
from schemas.admin import DistributionStats, SearchTimingMetrics
from services.search_funnel_metrics import resolve_time_range


AGGREGATION_NOTES = (
    "세션: search_events 를 user_id·keyword·created_at 정렬 후, "
    "같은 user_id+keyword 에서 이전 이벤트와의 시간 차가 session_gap_seconds 초를 넘기면 세션을 끊습니다. "
    "click_to_search_start: 세션 내 시간순 첫 search_click 이후 등장하는 첫 search_start 까지의 초. "
    "search_start_to_exit: 세션 내 첫 search_start 이후 등장하는 첫 search_exit 까지의 초 "
    "(검색 목록 이탈까지 체류; 인지부담 지표로 해석 가능). "
    "해당 이벤트가 없거나 순서가 맞지 않으면 그 세션은 해당 지표에서 제외됩니다."
)


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _stats(values: list[float]) -> DistributionStats:
    if not values:
        return DistributionStats(n=0, mean_seconds=None, p50_seconds=None, p90_seconds=None)
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    p50 = _percentile(s, 0.5)
    p90 = _percentile(s, 0.9)
    return DistributionStats(
        n=n,
        mean_seconds=round(mean, 3),
        p50_seconds=round(p50, 3) if p50 is not None else None,
        p90_seconds=round(p90, 3) if p90 is not None else None,
    )


def _split_sessions(
    events: list[SearchEvent],
    gap: timedelta,
) -> list[list[SearchEvent]]:
    if not events:
        return []
    sessions: list[list[SearchEvent]] = []
    cur: list[SearchEvent] = [events[0]]
    for e in events[1:]:
        prev = cur[-1]
        if e.user_id != prev.user_id or e.keyword != prev.keyword:
            sessions.append(cur)
            cur = [e]
            continue
        if e.created_at - prev.created_at > gap:
            sessions.append(cur)
            cur = [e]
        else:
            cur.append(e)
    sessions.append(cur)
    return sessions


def _session_click_to_start_seconds(session: list[SearchEvent]) -> float | None:
    ordered = sorted(session, key=lambda x: x.created_at)
    t_click = None
    for e in ordered:
        if e.event_type == "search_click":
            t_click = e.created_at
            break
    if t_click is None:
        return None
    for e in ordered:
        if e.event_type == "search_start" and e.created_at >= t_click:
            return (e.created_at - t_click).total_seconds()
    return None


def _session_start_to_exit_seconds(session: list[SearchEvent]) -> float | None:
    ordered = sorted(session, key=lambda x: x.created_at)
    t_start = None
    for e in ordered:
        if e.event_type == "search_start":
            t_start = e.created_at
            break
    if t_start is None:
        return None
    for e in ordered:
        if e.event_type == "search_exit" and e.created_at >= t_start:
            return (e.created_at - t_start).total_seconds()
    return None


def build_search_timing_metrics(
    db: Session,
    *,
    start,
    end,
    session_gap_seconds: int = 300,
) -> SearchTimingMetrics:
    if session_gap_seconds < 30 or session_gap_seconds > 86400:
        raise ValueError("session_gap_seconds must be between 30 and 86400")

    start_utc, end_utc = resolve_time_range(start, end)
    gap = timedelta(seconds=session_gap_seconds)

    rows = db.scalars(
        select(SearchEvent)
        .where(
            SearchEvent.created_at >= start_utc,
            SearchEvent.created_at <= end_utc,
        )
        .order_by(
            SearchEvent.user_id,
            SearchEvent.keyword,
            SearchEvent.created_at,
        )
    ).all()

    sessions = _split_sessions(list(rows), gap)

    click_to_start_vals: list[float] = []
    start_to_exit_vals: list[float] = []

    for sess in sessions:
        c2s = _session_click_to_start_seconds(sess)
        if c2s is not None and c2s >= 0:
            click_to_start_vals.append(c2s)

        s2e = _session_start_to_exit_seconds(sess)
        if s2e is not None and s2e >= 0:
            start_to_exit_vals.append(s2e)

    return SearchTimingMetrics(
        range_start_utc=start_utc,
        range_end_utc=end_utc,
        session_gap_seconds=session_gap_seconds,
        source_table="search_events",
        sessions_total=len(sessions),
        aggregation_notes=AGGREGATION_NOTES,
        click_to_search_start=_stats(click_to_start_vals),
        search_start_to_exit=_stats(start_to_exit_vals),
    )
