"""Authentication-related endpoints (placeholder for now).

This router will host:
- POST /auth/login
- GET  /auth/me
- POST /auth/register (later)
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

