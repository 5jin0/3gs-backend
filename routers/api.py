"""Root-level endpoints that don't belong to a specific domain."""

from fastapi import APIRouter

router = APIRouter(tags=["root"])


@router.get("/")
def root() -> dict:
    return {"message": "PangyoPass backend is running"}

