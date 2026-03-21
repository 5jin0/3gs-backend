"""관리자 전용 API (스캐폴드).

이후 집계·대시보드용 엔드포인트를 이 라우터에 추가합니다.
각 엔드포인트는 `require_admin`으로 보호됩니다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.messages import MSG_OK
from dependencies.auth import require_admin
from schemas.auth import UserPublic
from schemas.common import ApiResponse

AdminUser = Annotated[UserPublic, Depends(require_admin)]

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
