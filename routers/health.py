"""Health check endpoints.

Used by load balancers / monitoring and for quick sanity checks in development.
"""

from fastapi import APIRouter

router = APIRouter(
    tags=["health"],
)


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok"}

