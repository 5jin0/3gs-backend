"""관리자 전용 API (스캐폴드).

이후 집계·대시보드용 엔드포인트를 이 라우터에 추가합니다.
각 엔드포인트는 `require_admin`으로 보호됩니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.messages import MSG_FETCH_SUCCESS, MSG_OK
from dependencies.auth import require_admin
from dependencies.db import get_db
from schemas.admin import (
    AdminMetricsOverview,
    AdminOverview,
    AdminSaveListResult,
    AdminTermListResult,
    AdminUserListResult,
    SearchFunnelMetrics,
)
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from services.admin_lists import (
    build_admin_overview,
    list_admin_saves,
    list_admin_terms,
    list_admin_users,
)
from services.admin_metrics import build_admin_metrics_overview
from services.search_funnel_metrics import build_search_funnel_metrics
from sqlalchemy.orm import Session

AdminUser = Annotated[UserPublic, Depends(require_admin)]

_DEFAULT_LIST_LIMIT = 100
_MAX_LIST_LIMIT = 500

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get(
    "/ping",
    response_model=ApiResponse[dict],
    summary="관리자 API 연결 확인",
    description="Bearer 토큰과 DB상 관리자 권한이 있으면 200을 반환합니다.",
)
def admin_ping(_: AdminUser) -> ApiResponse[dict]:
    """스모크 테스트용. 실제 메트릭은 후속 엔드포인트에서 제공."""
    return ApiResponse(
        success=True,
        data={"ok": True},
        message=MSG_OK,
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserPublic],
    summary="현재 관리자 사용자 (DB 기준)",
)
def admin_me(admin: AdminUser) -> ApiResponse[UserPublic]:
    """`require_admin`을 통과한 사용자 정보를 그대로 돌려줍니다."""
    return ApiResponse(success=True, data=admin, message=MSG_OK)


@router.get(
    "/metrics/overview",
    response_model=ApiResponse[AdminMetricsOverview],
    summary="대시보드용 메트릭 요약",
    description="누적(totals) 및 최근 N일(recent, created_at 기준) 집계를 반환합니다.",
)
def admin_metrics_overview(
    _: AdminUser,
    db: Session = Depends(get_db),
    recent_days: int = Query(
        7,
        ge=1,
        le=365,
        description="recent 블록에 사용할 일 수 (기본 7일)",
    ),
) -> ApiResponse[AdminMetricsOverview]:
    overview = build_admin_metrics_overview(db, recent_days=recent_days)
    return ApiResponse(success=True, data=overview, message=MSG_OK)


@router.get(
    "/metrics/search-funnel",
    response_model=ApiResponse[SearchFunnelMetrics],
    summary="검색 퍼널 비율·검색 실패율",
    description=(
        "`search_events` 테이블만 사용합니다. "
        "비율·분모 정의는 응답 스키마 필드 description 과 동일합니다. "
        "`start`/`end` 를 모두 생략하면 UTC 기준 최근 7일입니다."
    ),
)
def admin_search_funnel(
    _: AdminUser,
    db: Session = Depends(get_db),
    start: datetime | None = Query(
        None,
        description="집계 구간 시작(포함). timezone 없으면 UTC로 간주.",
    ),
    end: datetime | None = Query(
        None,
        description="집계 구간 끝(포함). 생략 시 현재 시각(UTC).",
    ),
) -> ApiResponse[SearchFunnelMetrics]:
    try:
        data = build_search_funnel_metrics(db, start=start, end=end)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(success=True, data=data, message=MSG_OK)


@router.get(
    "/overview",
    response_model=ApiResponse[AdminOverview],
    summary="관리자 개요 (핵심 카운트)",
    description="비관리자 403, 미인증 401.",
)
def admin_overview(_: AdminUser, db: Session = Depends(get_db)) -> ApiResponse[AdminOverview]:
    data = build_admin_overview(db)
    return ApiResponse(success=True, data=data, message=MSG_OK)


@router.get(
    "/users",
    response_model=ApiResponse[AdminUserListResult],
    summary="사용자 목록",
)
def admin_users(
    _: AdminUser,
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(
        _DEFAULT_LIST_LIMIT,
        ge=1,
        le=_MAX_LIST_LIMIT,
        description="페이지 크기",
    ),
) -> ApiResponse[AdminUserListResult]:
    result = list_admin_users(db, offset=offset, limit=limit)
    return ApiResponse(success=True, data=result, message=MSG_FETCH_SUCCESS)


@router.get(
    "/terms",
    response_model=ApiResponse[AdminTermListResult],
    summary="용어(사전) 전체 목록",
)
def admin_terms(
    _: AdminUser,
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(
        _DEFAULT_LIST_LIMIT,
        ge=1,
        le=_MAX_LIST_LIMIT,
    ),
) -> ApiResponse[AdminTermListResult]:
    result = list_admin_terms(db, offset=offset, limit=limit)
    return ApiResponse(success=True, data=result, message=MSG_FETCH_SUCCESS)


@router.get(
    "/saves",
    response_model=ApiResponse[AdminSaveListResult],
    summary="전 사용자 단어장 저장 이력",
)
def admin_saves(
    _: AdminUser,
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(
        _DEFAULT_LIST_LIMIT,
        ge=1,
        le=_MAX_LIST_LIMIT,
    ),
) -> ApiResponse[AdminSaveListResult]:
    result = list_admin_saves(db, offset=offset, limit=limit)
    return ApiResponse(success=True, data=result, message=MSG_FETCH_SUCCESS)
