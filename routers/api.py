"""Root-level endpoints that don't belong to a specific domain."""

from fastapi import APIRouter

from app.core.messages import MSG_OK
from schemas.common import ApiResponse

router = APIRouter(tags=["root"])


@router.get("/")
def root() -> ApiResponse[dict]:
    return ApiResponse(
        success=True,
        data={"service": "PangyoPass backend is running"},
        message=MSG_OK,
    )

