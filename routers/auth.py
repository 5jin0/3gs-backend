"""Authentication-related endpoints (placeholder for now).

This router will host:
- POST /auth/login
- GET  /auth/me
- POST /auth/register (later)
"""

import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.models.user import User
from schemas.auth import LoginRequest, LoginResponse, UserPublic

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


_TEST_EMAIL = "test@pangyopass.com"
_TEST_PASSWORD = "password1234"


def _hash_password(password: str) -> str:
    """Temporary password hashing.

    Uses SHA-256 for now to keep dependencies minimal at this step.
    Step 13 will replace this with bcrypt/passlib.
    """

    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return f"sha256${digest}"


def _verify_password(plain_password: str, stored_password_hash: str) -> bool:
    """Verify password hash in constant time."""

    if not stored_password_hash.startswith("sha256$"):
        return False

    expected = _hash_password(plain_password)
    return hmac.compare_digest(expected, stored_password_hash)


def _get_or_create_test_user(db: Session) -> User:
    """Ensure a local test user exists for initial frontend integration."""

    existing_user = db.scalar(select(User).where(User.email == _TEST_EMAIL))
    if existing_user is not None:
        return existing_user

    new_user = User(
        email=_TEST_EMAIL,
        password_hash=_hash_password(_TEST_PASSWORD),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login (DB-based user authentication)",
    responses={
        200: {
            "description": "Login success",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "user": {"id": "user_1", "email": "test@pangyopass.com"},
                    }
                }
            },
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {"example": {"detail": "Invalid email or password"}}
            },
        },
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate user and return a token.

    Temporary flow:
    - query user by email from DB
    - verify password hash
    - issue JWT token on success
    """

    db_user = db.scalar(select(User).where(User.email == payload.email))
    if db_user is None:
        # Seed one local test account when no user exists yet.
        if payload.email == _TEST_EMAIL:
            db_user = _get_or_create_test_user(db)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

    if not _verify_password(payload.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    settings = get_settings()
    access_token = create_access_token(
        subject=str(db_user.id),
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        expires_minutes=settings.access_token_expire_minutes,
        extra_claims={"email": db_user.email},
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublic(id=str(db_user.id), email=db_user.email, created_at=db_user.created_at),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user (temporary)",
    responses={
        200: {
            "description": "Current user",
            "content": {
                "application/json": {
                    "example": {"id": "user_1", "email": "test@pangyopass.com"}
                }
            },
        },
        401: {
            "description": "Invalid or missing token",
            "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
        },
    },
)
def me(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    return current_user

