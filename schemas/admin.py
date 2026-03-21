"""관리자 API 응답 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
