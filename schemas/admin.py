"""관리자 API 응답 스키마."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminTotalsBlock(BaseModel):
    """전체(누적) 지표."""

    users: int = Field(..., ge=0, description="가입 사용자 수")
    terms: int = Field(..., ge=0, description="용어(사전) 행 수")
    saved_terms: int = Field(..., ge=0, description="단어장 저장 행 수 (user×term)")
    repeat_search_log_rows: int = Field(
        ...,
        ge=0,
        description="반복 검색 로그 행 수 (시간 구간 없음)",
    )
    user_access_events: int = Field(..., ge=0)
    user_access_login_success: int = Field(..., ge=0)
    user_access_wordbook_view: int = Field(..., ge=0)
    search_events: int = Field(..., ge=0)
    search_analytics_events: int = Field(..., ge=0)
    wordbook_save_events: int = Field(..., ge=0)
    wordbook_counter_save_click_sum: int = Field(
        ...,
        ge=0,
        description="wordbook_counters.save_click_count 합",
    )
    wordbook_counter_save_success_sum: int = Field(..., ge=0)
    wordbook_counter_wordbook_view_sum: int = Field(..., ge=0)


class AdminRecentBlock(BaseModel):
    """최근 N일 창구 내 지표 (created_at 기준)."""

    new_users: int = Field(..., ge=0)
    new_terms: int = Field(..., ge=0)
    new_saved_terms: int = Field(..., ge=0)
    user_access_events: int = Field(..., ge=0)
    user_access_login_success: int = Field(..., ge=0)
    user_access_wordbook_view: int = Field(..., ge=0)
    search_events: int = Field(..., ge=0)
    search_analytics_events: int = Field(..., ge=0)
    wordbook_save_events: int = Field(..., ge=0)


class AdminMetricsOverview(BaseModel):
    """대시보드용 요약 스냅샷."""

    generated_at_utc: datetime = Field(..., description="집계 시각 (UTC)")
    recent_days: int = Field(..., ge=1, le=365, description="recent 블록에 적용된 일 수")
    recent_cutoff_utc: datetime = Field(..., description="recent 창의 시작 시각 (UTC, inclusive)")
    totals: AdminTotalsBlock
    recent: AdminRecentBlock


class AdminOverview(BaseModel):
    """개요 대시보드용 핵심 카운트 (GET /admin/overview)."""

    user_count: int = Field(..., ge=0)
    term_count: int = Field(..., ge=0)
    saved_term_count: int = Field(..., ge=0)
    generated_at_utc: datetime = Field(..., description="집계 시각 (UTC)")


class AdminUserListItem(BaseModel):
    """사용자 목록 한 행."""

    id: str = Field(..., description="사용자 ID (문자열)")
    email: str = Field(..., description="DB 이메일")
    username: str = Field(
        ...,
        description="UserPublic과 동일하게 email과 같은 값",
    )
    is_admin: bool = False
    created_at: datetime


class AdminTermListItem(BaseModel):
    """용어 목록 한 행. 검색 API(TermSearchItem)와 동일한 의미 필드 매핑."""

    model_config = ConfigDict(
        populate_by_name=True,
        ser_json_by_alias=True,
    )

    id: int
    term: str
    meaning: str = Field(
        ...,
        description="DB `definition`(엑셀 '뜻') — TermSearchItem.meaning 과 동일",
    )
    original_meaning: str = Field(
        default="",
        serialization_alias="originalMeaning",
        description="엑셀 '원래 의미'",
    )
    example: str = ""
    created_at: datetime
    updated_at: datetime


class AdminSaveListItem(BaseModel):
    """전역 단어장 저장 이력 한 행."""

    id: int = Field(..., description="saved_terms.id")
    user_id: int
    term_id: int
    term: str = Field(..., description="용어 표기 (terms.term)")
    saved_at: datetime = Field(..., description="저장 시각 (saved_terms.created_at)")


class AdminUserListResult(BaseModel):
    items: list[AdminUserListItem]
    total: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)


class AdminTermListResult(BaseModel):
    items: list[AdminTermListItem]
    total: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)


class AdminSaveListResult(BaseModel):
    items: list[AdminSaveListItem]
    total: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)


class SearchFunnelEventCounts(BaseModel):
    """`search_events` 기간 내 event_type 건수 (행 단위, 중복 허용)."""

    search_start: int = Field(0, ge=0)
    search_click: int = Field(0, ge=0)
    suggestion_select: int = Field(0, ge=0)
    search_complete: int = Field(0, ge=0)
    search_exit: int = Field(0, ge=0)
    other: int = Field(
        0,
        ge=0,
        description="위 알려진 타입 외 event_type 합계(버전 차이 대비)",
    )
    total_events: int = Field(0, ge=0, description="기간 내 search_events 전체 행 수")


class SearchFunnelDistinctUsers(BaseModel):
    """기간 내 유저 수(중복 제거)."""

    unique_users_with_any_event: int = Field(
        ...,
        ge=0,
        description="기간 내 search_events 가 1건 이상인 서로 다른 user_id 수",
    )
    unique_users_with_search_start: int = Field(
        ...,
        ge=0,
        description="기간 내 search_start 가 1건 이상인 서로 다른 user_id 수",
    )


class SearchFunnelRates(BaseModel):
    """비율. 분모가 0이면 null. 소수는 반올림된 값."""

    search_start_rate: float | None = Field(
        None,
        description=(
            "검색 시작률: unique_users_with_search_start / unique_users_with_any_event. "
            "‘검색 이벤트가 있는 유저’ 중 ‘검색 시작 이벤트를 낸 유저’ 비율."
        ),
    )
    search_start_share_of_tracked_events: float | None = Field(
        None,
        description="search_start 건수 / total_events (전체 추적 이벤트 중 시작 이벤트 비중)",
    )
    search_click_rate: float | None = Field(
        None,
        description="검색 클릭률: search_click / search_start (시작 대비 결과 클릭)",
    )
    suggestion_select_rate: float | None = Field(
        None,
        description="자동완성 제안 클릭률: suggestion_select / search_start",
    )
    search_complete_rate: float | None = Field(
        None,
        description="검색 완료 비율: search_complete / search_start",
    )
    search_failure_rate: float | None = Field(
        None,
        description="검색 실패율: 1 - (search_complete / search_start). search_start=0 이면 null",
    )


class SearchFunnelMetrics(BaseModel):
    """관리자용 검색 퍼널 집계 (MVP: `search_events` 단일 소스)."""

    range_start_utc: datetime = Field(..., description="집계 구간 시작(UTC, 포함)")
    range_end_utc: datetime = Field(..., description="집계 구간 끝(UTC, 포함)")
    source_table: str = Field(
        "search_events",
        description="집계에 사용한 테이블명 (search_analytics_events 미포함)",
    )
    counts: SearchFunnelEventCounts
    distinct_users: SearchFunnelDistinctUsers
    rates: SearchFunnelRates


class DistributionStats(BaseModel):
    """연속형 지표 분포 (초 단위). 표본이 없으면 mean/p50/p90 은 null."""

    n: int = Field(..., ge=0, description="표본 수(세션 또는 쌍 개수)")
    mean_seconds: float | None = Field(None, description="산술 평균(초)")
    p50_seconds: float | None = Field(None, description="중앙값(초)")
    p90_seconds: float | None = Field(None, description="90 백분위(초)")


class SearchTimingMetrics(BaseModel):
    """검색 이벤트 간 시간차·이탈(인지부담 프록시).

    세션 정의·지표 해석은 `aggregation_notes` 참고.
    """

    range_start_utc: datetime
    range_end_utc: datetime
    session_gap_seconds: int = Field(
        ...,
        description="동일 user_id+keyword 내에서 이전 이벤트와의 간격이 이 값(초) 초과 시 새 세션",
    )
    source_table: str = Field("search_events", description="집계 소스 테이블")
    sessions_total: int = Field(..., ge=0, description="분리된 세션 수")
    aggregation_notes: str = Field(
        ...,
        description="집계 규칙 요약(클라이언트·문서와 공유)",
    )
    click_to_search_start: DistributionStats = Field(
        ...,
        description="검색창 클릭(search_click) 후 첫 검색 입력 시작(search_start)까지 경과(초)",
    )
    search_start_to_exit: DistributionStats = Field(
        ...,
        description=(
            "검색 입력 시작(search_start) 후 첫 목록 이탈(search_exit)까지 경과(초). "
            "인지부담(이탈 시각 − 입력 시작 시각)과 동일 정의로 사용 가능."
        ),
    )


class AccessLoginSummary(BaseModel):
    """기간 내 접속·로그인 이벤트 요약 (`user_access_events`)."""

    range_start_utc: datetime
    range_end_utc: datetime
    login_success_total: int = Field(..., ge=0, description="login_success 행 수")
    wordbook_view_total: int = Field(..., ge=0, description="wordbook_view 행 수(서비스 접속 프록시)")
    unique_users_with_login_success: int = Field(
        ...,
        ge=0,
        description="기간 내 login_success 가 1건 이상인 서로 다른 user_id 수",
    )
    unique_users_with_wordbook_view: int = Field(
        ...,
        ge=0,
        description="기간 내 wordbook_view 가 1건 이상인 서로 다른 user_id 수",
    )


class RegistrationCohortRow(BaseModel):
    """가입일(UTC) ISO 주차별 코호트."""

    cohort_id: str = Field(..., description="예: 2026-W11")
    cohort_label: str = Field(..., description="표시용 라벨")
    users_registered: int = Field(..., ge=0, description="해당 주에 가입한 사용자 수")
    reaccess_d7_users: int = Field(
        ...,
        ge=0,
        description="가입 후 7일 이내 login_success 가 2회 이상인 사용자 수",
    )
    reaccess_d7_rate: float | None = Field(
        None,
        description="reaccess_d7_users / users_registered",
    )


class SearchAnalyticsCohortRow(BaseModel):
    """SearchAnalyticsEvent.cohort 값별 요약."""

    cohort: str = Field(..., examples=["new_user", "existing_user"])
    unique_users_with_events: int = Field(
        ...,
        ge=0,
        description="기간 내 해당 cohort 로 이벤트가 1건 이상인 서로 다른 user_id 수",
    )
    users_with_login_reaccess: int = Field(
        ...,
        ge=0,
        description="같은 기간에 login_success 가 2건 이상인 사용자 수(재로그인 프록시)",
    )
    login_reaccess_rate: float | None = Field(
        None,
        description="users_with_login_reaccess / unique_users_with_events",
    )


class CohortReaccessMetrics(BaseModel):
    """로그인·접속 요약 + 코호트별 재접속률."""

    range_start_utc: datetime
    range_end_utc: datetime
    cohort_mode: Literal["registration_week", "search_analytics"]
    access_login_summary: AccessLoginSummary
    registration_cohorts: list[RegistrationCohortRow] | None = Field(
        None,
        description="cohort_mode=registration_week 일 때만 채움",
    )
    search_analytics_cohorts: list[SearchAnalyticsCohortRow] | None = Field(
        None,
        description="cohort_mode=search_analytics 일 때만 채움",
    )
    aggregation_notes: str = Field(..., description="집계 규칙")


class RetentionCohortRow(BaseModel):
    """리텐션 매트릭스 한 코호트 행."""

    cohort_id: str = Field(..., description="granularity 에 따라 가입일/주/월 키")
    cohort_label: str = Field(..., description="표시용")
    cohort_size: int = Field(..., ge=0, description="코호트에 포함된 가입자 수")
    retention: dict[str, float] = Field(
        ...,
        description='기간 인덱스(문자열 "0","1",...) → 해당 period 에 활동한 유저 비율',
    )


class RetentionMetrics(BaseModel):
    """가입 코호트 × period 리텐션 (활동=login_success)."""

    range_start_utc: datetime = Field(
        ...,
        description="가입일(users.created_at) 필터 구간 시작(포함)",
    )
    range_end_utc: datetime = Field(..., description="가입일 필터 구간 끝(포함)")
    granularity: Literal["day", "week", "month"] = Field(
        ...,
        description="코호트 묶음 단위 및 period 길이 정의",
    )
    activity_event: str = Field(
        "login_success",
        description="활성으로 본 이벤트 타입",
    )
    max_periods_included: int = Field(
        ...,
        ge=0,
        description="period 0..max (포함) 까지 계산",
    )
    cohorts: list[RetentionCohortRow]
    aggregation_notes: str = Field(..., description="집계 규칙 상세")


class AdminUserSaveCountItem(BaseModel):
    """유저별 단어장 저장 건수 (saved_terms 기준)."""

    user_id: int = Field(..., ge=1)
    email: str
    username: str = Field(..., description="UserPublic 과 동일하게 email 과 동일 값")
    save_count: int = Field(..., ge=0, description="필터 구간 내 저장 행 수(또는 전체)")
    first_saved_at: datetime | None = Field(
        None,
        description="필터가 있으면 그 안에서의 최초 저장 시각",
    )
    last_saved_at: datetime | None = Field(
        None,
        description="필터가 있으면 그 안에서의 마지막 저장 시각",
    )


class AdminUserSaveCountResult(BaseModel):
    items: list[AdminUserSaveCountItem]
    total: int = Field(..., ge=0, description="집계 대상 유저 수(저장 1건 이상인 유저)")
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    saved_from_utc: datetime | None = Field(
        None,
        description="saved_terms.created_at 하한(포함). null 이면 제한 없음",
    )
    saved_to_utc: datetime | None = Field(
        None,
        description="saved_terms.created_at 상한(포함). null 이면 제한 없음",
    )
    source_table: str = Field("saved_terms", description="집계 소스")
