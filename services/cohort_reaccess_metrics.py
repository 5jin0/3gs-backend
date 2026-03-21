"""로그인·접속 요약 및 코호트별 재접속(재로그인) 지표."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.search_analytics_event import SearchAnalyticsEvent
from db.models.user import User
from db.models.user_access_event import UserAccessEvent
from schemas.admin import (
    AccessLoginSummary,
    CohortReaccessMetrics,
    RegistrationCohortRow,
    SearchAnalyticsCohortRow,
)
from services.search_funnel_metrics import resolve_time_range


AGGREGATION_NOTES = (
    "access_login_summary: user_access_events 테이블에서 created_at 이 구간에 드는 행만 집계. "
    "registration_week: users.created_at 이 [start,end] 에 포함된 사용자만 코호트에 넣고, "
    "가입일(created_at)이 속한 ISO 주(UTC)로 묶음. "
    "reaccess_d7: 해당 사용자의 login_success 가 [가입일, 가입일+7일] 구간에 2건 이상이면 재접속으로 간주. "
    "search_analytics: SearchAnalyticsEvent 의 cohort 값으로 묶고, "
    "해당 기간·코호트에 이벤트가 있는 user_id 에 대해 같은 기간 내 login_success 가 2건 이상이면 재접속으로 간주."
)


def _ensure_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_week_id(d) -> str:
    d = _ensure_utc(d)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _count_login_success_in_range(
    db: Session,
    *,
    user_id: int,
    start,
    end,
) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(UserAccessEvent)
            .where(
                UserAccessEvent.user_id == user_id,
                UserAccessEvent.event_type == "login_success",
                UserAccessEvent.created_at >= start,
                UserAccessEvent.created_at <= end,
            )
        )
        or 0
    )


def build_access_login_summary(db: Session, start_utc, end_utc) -> AccessLoginSummary:
    login_total = int(
        db.scalar(
            select(func.count())
            .select_from(UserAccessEvent)
            .where(
                UserAccessEvent.event_type == "login_success",
                UserAccessEvent.created_at >= start_utc,
                UserAccessEvent.created_at <= end_utc,
            )
        )
        or 0
    )
    wb_total = int(
        db.scalar(
            select(func.count())
            .select_from(UserAccessEvent)
            .where(
                UserAccessEvent.event_type == "wordbook_view",
                UserAccessEvent.created_at >= start_utc,
                UserAccessEvent.created_at <= end_utc,
            )
        )
        or 0
    )
    u_login = int(
        db.scalar(
            select(func.count(func.distinct(UserAccessEvent.user_id)))
            .where(
                UserAccessEvent.event_type == "login_success",
                UserAccessEvent.created_at >= start_utc,
                UserAccessEvent.created_at <= end_utc,
            )
        )
        or 0
    )
    u_wb = int(
        db.scalar(
            select(func.count(func.distinct(UserAccessEvent.user_id)))
            .where(
                UserAccessEvent.event_type == "wordbook_view",
                UserAccessEvent.created_at >= start_utc,
                UserAccessEvent.created_at <= end_utc,
            )
        )
        or 0
    )

    return AccessLoginSummary(
        range_start_utc=start_utc,
        range_end_utc=end_utc,
        login_success_total=login_total,
        wordbook_view_total=wb_total,
        unique_users_with_login_success=u_login,
        unique_users_with_wordbook_view=u_wb,
    )


def _registration_cohort_rows(
    db: Session,
    start_utc,
    end_utc,
) -> list[RegistrationCohortRow]:
    users = db.scalars(
        select(User).where(
            User.created_at >= start_utc,
            User.created_at <= end_utc,
        )
    ).all()

    by_week: dict[str, list[User]] = defaultdict(list)
    for u in users:
        by_week[_iso_week_id(u.created_at)].append(u)

    rows: list[RegistrationCohortRow] = []
    for cohort_id in sorted(by_week.keys()):
        ulist = by_week[cohort_id]
        n = len(ulist)
        re_d7 = 0
        for u in ulist:
            reg = _ensure_utc(u.created_at)
            window_end = reg + timedelta(days=7)
            c = _count_login_success_in_range(
                db, user_id=u.id, start=reg, end=window_end
            )
            if c >= 2:
                re_d7 += 1
        rate = round(re_d7 / n, 6) if n > 0 else None
        rows.append(
            RegistrationCohortRow(
                cohort_id=cohort_id,
                cohort_label=f"UTC ISO week {cohort_id}",
                users_registered=n,
                reaccess_d7_users=re_d7,
                reaccess_d7_rate=rate,
            )
        )
    return rows


def _search_analytics_cohort_rows(
    db: Session,
    start_utc,
    end_utc,
) -> list[SearchAnalyticsCohortRow]:
    ev_rows = db.execute(
        select(SearchAnalyticsEvent.cohort, SearchAnalyticsEvent.user_id)
        .where(
            SearchAnalyticsEvent.created_at >= start_utc,
            SearchAnalyticsEvent.created_at <= end_utc,
        )
        .distinct()
    ).all()

    cohort_users: dict[str, set[int]] = defaultdict(set)
    for cohort, uid in ev_rows:
        cohort_users[cohort].add(int(uid))

    out: list[SearchAnalyticsCohortRow] = []
    for cohort in sorted(cohort_users.keys()):
        uids = cohort_users[cohort]
        n = len(uids)
        re_cnt = 0
        for uid in uids:
            if (
                _count_login_success_in_range(
                    db,
                    user_id=uid,
                    start=start_utc,
                    end=end_utc,
                )
                >= 2
            ):
                re_cnt += 1
        rate = round(re_cnt / n, 6) if n > 0 else None
        out.append(
            SearchAnalyticsCohortRow(
                cohort=cohort,
                unique_users_with_events=n,
                users_with_login_reaccess=re_cnt,
                login_reaccess_rate=rate,
            )
        )
    return out


def build_cohort_reaccess_metrics(
    db: Session,
    *,
    start,
    end,
    cohort_mode: Literal["registration_week", "search_analytics"],
) -> CohortReaccessMetrics:
    start_utc, end_utc = resolve_time_range(start, end)
    access = build_access_login_summary(db, start_utc, end_utc)

    reg_rows: list[RegistrationCohortRow] | None = None
    sa_rows: list[SearchAnalyticsCohortRow] | None = None

    if cohort_mode == "registration_week":
        reg_rows = _registration_cohort_rows(db, start_utc, end_utc)
    else:
        sa_rows = _search_analytics_cohort_rows(db, start_utc, end_utc)

    return CohortReaccessMetrics(
        range_start_utc=start_utc,
        range_end_utc=end_utc,
        cohort_mode=cohort_mode,
        access_login_summary=access,
        registration_cohorts=reg_rows,
        search_analytics_cohorts=sa_rows,
        aggregation_notes=AGGREGATION_NOTES,
    )
