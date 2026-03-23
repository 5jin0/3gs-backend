"""Next.js 관리자 앱이 기대하는 분석 API 응답 형태 (`/admin/analytics/*`)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SearchFunnelFrontendData(BaseModel):
    """GET .../search-funnel"""

    start_rate: Optional[float] = Field(None, description="0~1 또는 null")
    click_rate: Optional[float] = None
    autocomplete_rate: Optional[float] = None
    failure_rate: Optional[float] = None


class SearchUxFrontendData(BaseModel):
    """GET .../search-ux — search_start→exit 체류를 latency 로 사용."""

    latency_avg_ms: Optional[float] = None
    latency_p50_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    latency_p99_ms: Optional[float] = None
    abandonment_rate: Optional[float] = None
    churn_rate: Optional[float] = None
    cognitive_load_index: Optional[float] = None
    sample_size: int = 0
    sample_sufficient: bool = Field(
        False,
        description="표본이 충분하면 true (기본 n>=30)",
    )


class MatrixRow(BaseModel):
    label: str
    values: list[float]


class HeatmapMatrixData(BaseModel):
    """히트맵용 행렬."""

    column_labels: list[str] = Field(default_factory=list)
    rows: list[MatrixRow] = Field(default_factory=list)


class RetentionMatrixData(BaseModel):
    column_labels: list[str] = Field(default_factory=list)
    rows: list[MatrixRow] = Field(default_factory=list)
    granularity_label: Optional[str] = None


class UserSavedCountItemFrontend(BaseModel):
    user_id: int
    username: str
    email: str
    save_count: int


class UserSavedCountsFrontendData(BaseModel):
    items: list[UserSavedCountItemFrontend] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class UserWordbookReaccessItemFrontend(BaseModel):
    user_id: int
    username: str
    email: str
    wordbook_view_count: int = 0
    reaccess_count: int = 0
    reaccess_rate: Optional[float] = Field(
        None,
        description="reaccess_count / wordbook_view_count (0~1)",
    )


class UserWordbookReaccessFrontendData(BaseModel):
    items: list[UserWordbookReaccessItemFrontend] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
