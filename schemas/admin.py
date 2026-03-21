"""관리자 API 응답 스키마."""

from __future__ import annotations

from datetime import datetime

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
