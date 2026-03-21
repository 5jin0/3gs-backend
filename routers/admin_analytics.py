"""Next.js 관리자 분석 API (`PP_ADMIN_ANALYTICS_PREFIX`, 기본 `/admin/analytics`)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.messages import MSG_OK
from dependencies.auth import require_admin
from dependencies.db import get_db
from schemas.admin_analytics_frontend import (
    HeatmapMatrixData,
    RetentionMatrixData,
    SearchFunnelFrontendData,
    SearchUxFrontendData,
    UserSavedCountsFrontendData,
)
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from services.admin_analytics_frontend import (
    build_access_cohort_heatmap,
    build_retention_matrix_frontend,
    build_search_funnel_frontend,
    build_search_ux_frontend,
    build_user_saved_counts_frontend,
)
from sqlalchemy.orm import Session

AdminUser = Annotated[UserPublic, Depends(require_admin)]

router = APIRouter(tags=["admin-analytics"])


@router.get(
    "/search-funnel",
    response_model=ApiResponse[SearchFunnelFrontendData],
    summary="검색 퍼널 비율(프론트용)",
)
def analytics_search_funnel(
    _: AdminUser,
    db: Session = Depends(get_db),
    period: Literal["day", "week", "month"] = Query(
        "week",
        description="롤링 기간: day=1일, week=7일, month=30일(UTC)",
    ),
) -> ApiResponse[SearchFunnelFrontendData]:
    data = build_search_funnel_frontend(db, period=period)
    return ApiResponse(success=True, data=data, message=MSG_OK)


@router.get(
    "/search-ux",
    response_model=ApiResponse[SearchUxFrontendData],
    summary="검색 UX 지표(프론트용)",
)
def analytics_search_ux(
    _: AdminUser,
    db: Session = Depends(get_db),
    period: Literal["day", "week", "month"] = Query("week"),
) -> ApiResponse[SearchUxFrontendData]:
    data = build_search_ux_frontend(db, period=period)
    return ApiResponse(success=True, data=data, message=MSG_OK)


@router.get(
    "/access-cohorts",
    response_model=ApiResponse[HeatmapMatrixData],
    summary="접속·코호트 히트맵(프론트용)",
)
def analytics_access_cohorts(
    _: AdminUser,
    db: Session = Depends(get_db),
    period: Literal["day", "week", "month"] = Query("week"),
    group_by: Literal["signup_week", "first_visit", "all"] = Query(
        "signup_week",
        description="all: 전체 요약 한 행, signup_week: 가입 ISO 주, first_visit: search_analytics cohort",
    ),
) -> ApiResponse[HeatmapMatrixData]:
    data = build_access_cohort_heatmap(
        db,
        period=period,
        group_by=group_by,
    )
    return ApiResponse(success=True, data=data, message=MSG_OK)


@router.get(
    "/retention",
    response_model=ApiResponse[RetentionMatrixData],
    summary="리텐션 행렬(프론트용)",
)
def analytics_retention(
    _: AdminUser,
    db: Session = Depends(get_db),
    granularity: Literal["day", "week", "month"] = Query(
        "week",
        description="코호트·period 정의 (가입 코호트는 최근 90일 가입자)",
    ),
) -> ApiResponse[RetentionMatrixData]:
    data = build_retention_matrix_frontend(db, granularity=granularity)
    return ApiResponse(success=True, data=data, message=MSG_OK)


@router.get(
    "/user-saved-counts",
    response_model=ApiResponse[UserSavedCountsFrontendData],
    summary="유저별 저장 횟수(프론트용)",
)
def analytics_user_saved_counts(
    _: AdminUser,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    sort: str = Query(
        "save_count_desc",
        description="save_count_desc|save_count_asc|username_asc|username_desc",
    ),
) -> ApiResponse[UserSavedCountsFrontendData]:
    try:
        data = build_user_saved_counts_frontend(
            db,
            page=page,
            page_size=page_size,
            sort=sort,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(success=True, data=data, message=MSG_OK)
