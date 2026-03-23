"""Next.js 관리자 `/admin/analytics/*` 응답 조립."""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from db.models.search_event import SearchEvent
from db.models.user import User
from db.models.user_access_event import UserAccessEvent

from schemas.admin_analytics_frontend import (
    HeatmapMatrixData,
    MatrixRow,
    RetentionMatrixData,
    SearchFunnelFrontendData,
    SearchUxFrontendData,
    UserSavedCountItemFrontend,
    UserSavedCountsFrontendData,
    UserWordbookReaccessFrontendData,
    UserWordbookReaccessItemFrontend,
)
from services.admin_lists import list_user_save_counts
from services.cohort_reaccess_metrics import build_cohort_reaccess_metrics
from services.retention_metrics import build_retention_metrics
from services.search_funnel_metrics import build_search_funnel_metrics
from services.search_timing_metrics import build_search_timing_metrics


def period_to_datetime_range(
    period: Literal["day", "week", "month"],
) -> tuple[datetime, datetime]:
    """롤링 윈도우: day=1일, week=7일, month=30일(UTC)."""

    now = datetime.now(timezone.utc)
    if period == "day":
        start = now - timedelta(days=1)
    elif period == "week":
        start = now - timedelta(days=7)
    else:
        start = now - timedelta(days=30)
    return start, now


def default_retention_registration_window() -> tuple[datetime, datetime]:
    """리텐션 코호트 가입일 필터: 최근 90일(UTC)."""

    end = datetime.now(timezone.utc)
    return end - timedelta(days=90), end


def _interp_p95(p50: float | None, p90: float | None) -> float | None:
    if p50 is None or p90 is None:
        return None
    return float(p50) + (float(p90) - float(p50)) * 0.9


def _interp_p99(p90: float | None) -> float | None:
    if p90 is None:
        return None
    return float(p90) * 1.1


def _compute_cognitive_load_index_from_repeat_ratio(
    db: Session,
    *,
    start: datetime,
    end: datetime,
) -> float | None:
    """인지부담지수: 기간 내 '동일 용어 반복 검색 사용자 비율'."""

    total_users = int(
        db.scalar(
            select(func.count(func.distinct(SearchEvent.user_id))).where(
                SearchEvent.created_at >= start,
                SearchEvent.created_at <= end,
            )
        )
        or 0
    )
    if total_users <= 0:
        return None

    repeated_user_keyword_subq = (
        select(SearchEvent.user_id, SearchEvent.keyword)
        .where(
            SearchEvent.created_at >= start,
            SearchEvent.created_at <= end,
        )
        .group_by(SearchEvent.user_id, SearchEvent.keyword)
        .having(func.count(SearchEvent.id) >= 2)
        .subquery()
    )
    repeated_users = int(
        db.scalar(
            select(func.count(func.distinct(repeated_user_keyword_subq.c.user_id)))
        )
        or 0
    )

    return round(repeated_users / total_users, 6)


def build_search_funnel_frontend(
    db: Session,
    *,
    period: Literal["day", "week", "month"],
) -> SearchFunnelFrontendData:
    start, end = period_to_datetime_range(period)
    fm = build_search_funnel_metrics(db, start=start, end=end)
    r = fm.rates
    return SearchFunnelFrontendData(
        start_rate=r.search_start_rate,
        click_rate=r.search_click_rate,
        autocomplete_rate=r.suggestion_select_rate,
        failure_rate=r.search_failure_rate,
    )


def build_search_ux_frontend(
    db: Session,
    *,
    period: Literal["day", "week", "month"],
) -> SearchUxFrontendData:
    start, end = period_to_datetime_range(period)
    timing = build_search_timing_metrics(
        db,
        start=start,
        end=end,
        session_gap_seconds=300,
    )
    funnel = build_search_funnel_metrics(db, start=start, end=end)
    ex = timing.search_start_to_exit
    ct = timing.click_to_search_start

    def ms(sec: float | None) -> float | None:
        if sec is None:
            return None
        return round(float(sec) * 1000.0, 2)

    p50 = ex.p50_seconds
    p90 = ex.p90_seconds
    p95 = _interp_p95(p50, p90)
    p99 = _interp_p99(p90)

    c = funnel.counts
    abandonment: float | None = None
    if c.search_start > 0:
        abandonment = round(c.search_exit / c.search_start, 6)

    ci = _compute_cognitive_load_index_from_repeat_ratio(
        db,
        start=start,
        end=end,
    )

    n = ex.n
    return SearchUxFrontendData(
        latency_avg_ms=ms(ex.mean_seconds),
        latency_p50_ms=ms(p50),
        latency_p95_ms=ms(p95),
        latency_p99_ms=ms(p99),
        abandonment_rate=abandonment,
        churn_rate=funnel.rates.search_failure_rate,
        cognitive_load_index=ci,
        sample_size=n,
        sample_sufficient=n >= 30,
    )


def build_access_cohort_heatmap(
    db: Session,
    *,
    period: Literal["day", "week", "month"],
    group_by: Literal["signup_week", "first_visit", "all"],
) -> HeatmapMatrixData:
    start, end = period_to_datetime_range(period)

    if group_by == "all":
        cr = build_cohort_reaccess_metrics(
            db,
            start=start,
            end=end,
            cohort_mode="registration_week",
        )
        al = cr.access_login_summary
        return HeatmapMatrixData(
            column_labels=[
                "login_success_total",
                "wordbook_view_total",
                "unique_users_login_success",
                "unique_users_wordbook_view",
            ],
            rows=[
                MatrixRow(
                    label="all",
                    values=[
                        float(al.login_success_total),
                        float(al.wordbook_view_total),
                        float(al.unique_users_with_login_success),
                        float(al.unique_users_with_wordbook_view),
                    ],
                )
            ],
        )

    if group_by == "signup_week":
        cr = build_cohort_reaccess_metrics(
            db,
            start=start,
            end=end,
            cohort_mode="registration_week",
        )
        rows: list[MatrixRow] = []
        for row in cr.registration_cohorts or []:
            rr = row.reaccess_d7_rate if row.reaccess_d7_rate is not None else 0.0
            rows.append(
                MatrixRow(
                    label=row.cohort_id,
                    values=[
                        float(row.users_registered),
                        float(rr),
                        float(row.reaccess_d7_users),
                    ],
                )
            )
        return HeatmapMatrixData(
            column_labels=[
                "users_registered",
                "reaccess_d7_rate",
                "reaccess_d7_users",
            ],
            rows=rows,
        )

    # first_visit: search_analytics cohort 로 프록시
    cr = build_cohort_reaccess_metrics(
        db,
        start=start,
        end=end,
        cohort_mode="search_analytics",
    )
    rows2: list[MatrixRow] = []
    for row in cr.search_analytics_cohorts or []:
        rr = row.login_reaccess_rate if row.login_reaccess_rate is not None else 0.0
        rows2.append(
            MatrixRow(
                label=row.cohort,
                values=[
                    float(row.unique_users_with_events),
                    float(rr),
                    float(row.users_with_login_reaccess),
                ],
            )
        )
    return HeatmapMatrixData(
        column_labels=[
            "unique_users_with_events",
            "login_reaccess_rate",
            "users_with_login_reaccess",
        ],
        rows=rows2,
    )


def build_retention_matrix_frontend(
    db: Session,
    *,
    granularity: Literal["day", "week", "month"],
) -> RetentionMatrixData:
    start, end = default_retention_registration_window()
    mp_default = {"day": 14, "week": 8, "month": 6}[granularity]
    rm = build_retention_metrics(
        db,
        start=start,
        end=end,
        granularity=granularity,
        max_periods=mp_default,
    )
    column_labels = [str(i) for i in range(rm.max_periods_included + 1)]
    rows: list[MatrixRow] = []
    for c in rm.cohorts:
        vals = [
            float(c.retention.get(str(i), 0.0))
            for i in range(rm.max_periods_included + 1)
        ]
        rows.append(MatrixRow(label=c.cohort_id, values=vals))
    return RetentionMatrixData(
        column_labels=column_labels,
        rows=rows,
        granularity_label=granularity,
    )


def build_user_saved_counts_frontend(
    db: Session,
    *,
    page: int,
    page_size: int,
    sort: str,
) -> UserSavedCountsFrontendData:
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    offset = (page - 1) * page_size
    result = list_user_save_counts(
        db,
        offset=offset,
        limit=page_size,
        saved_from=None,
        saved_to=None,
        sort=sort,
    )
    items = [
        UserSavedCountItemFrontend(
            user_id=i.user_id,
            username=i.username,
            email=i.email,
            save_count=i.save_count,
        )
        for i in result.items
    ]
    return UserSavedCountsFrontendData(
        items=items,
        total=result.total,
        page=page,
        page_size=page_size,
    )


def build_user_wordbook_reaccess_frontend(
    db: Session,
    *,
    period: Literal["day", "week", "month"],
    page: int,
    page_size: int,
    sort: str,
) -> UserWordbookReaccessFrontendData:
    """유저별 단어장 조회 횟수와 재접속률(조회 이후 재로그인 비율)."""

    start, end = period_to_datetime_range(period)
    page = max(1, page)
    page_size = max(1, min(500, page_size))

    view_rows = db.execute(
        select(
            UserAccessEvent.user_id,
            func.count(UserAccessEvent.id).label("view_count"),
        )
        .where(
            UserAccessEvent.event_type == "wordbook_view",
            UserAccessEvent.created_at >= start,
            UserAccessEvent.created_at <= end,
        )
        .group_by(UserAccessEvent.user_id)
    ).all()

    if not view_rows:
        return UserWordbookReaccessFrontendData(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
        )

    user_ids = [int(r.user_id) for r in view_rows]
    view_count_by_user = {int(r.user_id): int(r.view_count) for r in view_rows}

    ev_rows = db.execute(
        select(
            UserAccessEvent.user_id,
            UserAccessEvent.event_type,
            UserAccessEvent.created_at,
        )
        .where(
            UserAccessEvent.user_id.in_(user_ids),
            UserAccessEvent.created_at >= start,
            UserAccessEvent.created_at <= end,
            UserAccessEvent.event_type.in_(["wordbook_view", "login_success"]),
        )
        .order_by(UserAccessEvent.user_id, UserAccessEvent.created_at)
    ).all()

    views_by_user: dict[int, list[datetime]] = {}
    logins_by_user: dict[int, list[datetime]] = {}
    for r in ev_rows:
        uid = int(r.user_id)
        ts = r.created_at
        if r.event_type == "wordbook_view":
            views_by_user.setdefault(uid, []).append(ts)
        elif r.event_type == "login_success":
            logins_by_user.setdefault(uid, []).append(ts)

    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    user_by_id = {int(u.id): u for u in users}

    items: list[UserWordbookReaccessItemFrontend] = []
    for uid in user_ids:
        u = user_by_id.get(uid)
        if u is None:
            continue
        views = views_by_user.get(uid, [])
        logins = logins_by_user.get(uid, [])
        reaccess_cnt = 0
        for view_ts in views:
            idx = bisect_right(logins, view_ts)
            if idx < len(logins):
                reaccess_cnt += 1
        view_count = view_count_by_user.get(uid, 0)
        rate = round(reaccess_cnt / view_count, 6) if view_count > 0 else None
        items.append(
            UserWordbookReaccessItemFrontend(
                user_id=uid,
                username=u.email,
                email=u.email,
                wordbook_view_count=view_count,
                reaccess_count=reaccess_cnt,
                reaccess_rate=rate,
            )
        )

    sort_key = sort.strip().lower()
    if sort_key == "wordbook_view_desc":
        items.sort(key=lambda x: (x.wordbook_view_count, x.user_id), reverse=True)
    elif sort_key == "wordbook_view_asc":
        items.sort(key=lambda x: (x.wordbook_view_count, x.user_id))
    elif sort_key == "reaccess_rate_desc":
        items.sort(
            key=lambda x: ((x.reaccess_rate if x.reaccess_rate is not None else -1.0), x.user_id),
            reverse=True,
        )
    elif sort_key == "reaccess_rate_asc":
        items.sort(
            key=lambda x: ((x.reaccess_rate if x.reaccess_rate is not None else 2.0), x.user_id),
        )
    elif sort_key == "username_desc":
        items.sort(key=lambda x: (x.username.lower(), x.user_id), reverse=True)
    elif sort_key == "username_asc":
        items.sort(key=lambda x: (x.username.lower(), x.user_id))
    else:
        raise ValueError(
            "sort must be one of: "
            "wordbook_view_desc, wordbook_view_asc, "
            "reaccess_rate_desc, reaccess_rate_asc, "
            "username_asc, username_desc"
        )

    total = len(items)
    offset = (page - 1) * page_size
    paged = items[offset : offset + page_size]
    return UserWordbookReaccessFrontendData(
        items=paged,
        total=total,
        page=page,
        page_size=page_size,
    )
