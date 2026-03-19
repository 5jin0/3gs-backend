"""Health check endpoints.

Used by load balancers / monitoring and for quick sanity checks in development.
"""

from fastapi import APIRouter

from app.core.messages import MSG_HEALTH_OK
from schemas.common import ApiResponse

router = APIRouter(
    tags=["health"],
)


@router.get("/health")
def health_check() -> ApiResponse[dict]:
    return ApiResponse(success=True, data={"status": "ok"}, message=MSG_HEALTH_OK)

