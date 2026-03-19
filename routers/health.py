"""Health check endpoints.

Used by load balancers / monitoring and for quick sanity checks in development.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok"}

