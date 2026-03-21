"""가입 코호트 기준 리텐션 (활동: login_success)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.user import User
from db.models.user_access_event import UserAccessEvent
from schemas.admin import RetentionCohortRow, RetentionMetrics
from services.cohort_reaccess_metrics import _iso_week_id
from services.search_funnel_metrics import resolve_time_range


AGGREGATION_NOTES = (
    "코호트: users.created_at 이 [start,end] 에 포함된 사용자만 포함. "
    "활성(리텐션): user_access_events.event_type=login_success 가 해당 기간에 1건 이상. "
    "granularity=day: 코호트는 가입일(UTC) 날짜. period N 은 가입일+N일 자정 구간의 캘린더 일에 로그인이 있는 비율. "
    "granularity=week: 코호트는 가입일이 속한 ISO 주. period N 은 가입일 기준 [+7N일, +7N+6일] 구간 내 로그인 비율. "
    "granularity=month: 코호트는 가입 연-월(UTC). period N 은 가입일 기준 [+30N일, +30(N+1)-1일] 구간(30일 블록) 내 로그인 비율."
)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _reg_date_utc(u: User) -> date:
    return _ensure_utc(u.created_at).date()


def _cohort_key(u: User, granularity: Literal["day", "week", "month"]) -> str:
    d = _reg_date_utc(u)
    if granularity == "day":
        return d.isoformat()
    if granularity == "week":
        return _iso_week_id(u.created_at)
    return f"{d.year:04d}-{d.month:02d}"


def _load_login_dates_by_user(
    db: Session,
    user_ids: list[int],
) -> dict[int, set[date]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(UserAccessEvent.user_id, UserAccessEvent.created_at).where(
            UserAccessEvent.user_id.in_(user_ids),
            UserAccessEvent.event_type == "login_success",
        )
    ).all()
    out: dict[int, set[date]] = defaultdict(set)
    for uid, ts in rows:
        out[int(uid)].add(_ensure_utc(ts).date())
    return dict(out)


def _active_day(
    login_dates: set[date],
    reg: date,
    period_index: int,
) -> bool:
    target = reg + timedelta(days=period_index)
    return target in login_dates


def _active_week_block(
    login_dates: set[date],
    reg: date,
    period_index: int,
) -> bool:
    start = reg + timedelta(days=7 * period_index)
    end = reg + timedelta(days=7 * period_index + 6)
    return any(start <= d <= end for d in login_dates)


def _active_month_block(
    login_dates: set[date],
    reg: date,
    period_index: int,
) -> bool:
    start = reg + timedelta(days=30 * period_index)
    end = reg + timedelta(days=30 * (period_index + 1) - 1)
    return any(start <= d <= end for d in login_dates)


def _default_max_periods(granularity: str) -> int:
    return {"day": 14, "week": 8, "month": 6}.get(granularity, 14)


def build_retention_metrics(
    db: Session,
    *,
    start,
    end,
    granularity: Literal["day", "week", "month"],
    max_periods: int | None,
) -> RetentionMetrics:
    start_utc, end_utc = resolve_time_range(start, end)
    mp = max_periods if max_periods is not None else _default_max_periods(granularity)
    if mp < 1 or mp > 52:
        raise ValueError("max_periods must be between 1 and 52")

    users = db.scalars(
        select(User).where(
            User.created_at >= start_utc,
            User.created_at <= end_utc,
        )
    ).all()

    uids = [u.id for u in users]
    login_by_user = _load_login_dates_by_user(db, uids)

    by_cohort: dict[str, list[User]] = defaultdict(list)
    for u in users:
        by_cohort[_cohort_key(u, granularity)].append(u)

    cohort_rows: list[RetentionCohortRow] = []
    for cohort_id in sorted(by_cohort.keys()):
        ulist = by_cohort[cohort_id]
        n = len(ulist)
        retention: dict[str, float] = {}
        for p in range(mp + 1):
            key = str(p)
            if n == 0:
                retention[key] = 0.0
                continue
            cnt = 0
            for u in ulist:
                reg = _reg_date_utc(u)
                ld = login_by_user.get(u.id, set())
                if granularity == "day":
                    ok = _active_day(ld, reg, p)
                elif granularity == "week":
                    ok = _active_week_block(ld, reg, p)
                else:
                    ok = _active_month_block(ld, reg, p)
                if ok:
                    cnt += 1
            retention[key] = round(cnt / n, 6)

        label = {
            "day": f"UTC signup day {cohort_id}",
            "week": f"UTC ISO signup week {cohort_id}",
            "month": f"UTC signup month {cohort_id}",
        }[granularity]

        cohort_rows.append(
            RetentionCohortRow(
                cohort_id=cohort_id,
                cohort_label=label,
                cohort_size=n,
                retention=retention,
            )
        )

    return RetentionMetrics(
        range_start_utc=start_utc,
        range_end_utc=end_utc,
        granularity=granularity,
        activity_event="login_success",
        max_periods_included=mp,
        cohorts=cohort_rows,
        aggregation_notes=AGGREGATION_NOTES,
    )
