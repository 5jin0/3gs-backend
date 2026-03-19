"""Authentication-related endpoints (placeholder for now).

This router will host:
- POST /auth/login
- GET  /auth/me
- POST /auth/register (later)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.messages import (
    AUTH_EMAIL_ALREADY_REGISTERED,
    AUTH_INVALID_CREDENTIALS,
    MSG_FETCH_SUCCESS,
    MSG_LOGIN_SUCCESS,
    MSG_REGISTER_SUCCESS,
)
from app.core.security import create_access_token, hash_password, verify_password
from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.models.user import User
from schemas.auth import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, UserPublic
from schemas.common import ApiResponse

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


_TEST_EMAIL = "test@pangyopass.com"
_TEST_PASSWORD = "password1234"


def _get_or_create_test_user(db: Session) -> User:
    """Ensure a local test user exists for initial frontend integration."""

    existing_user = db.scalar(select(User).where(User.email == _TEST_EMAIL))
    if existing_user is not None:
        return existing_user

    new_user = User(
        email=_TEST_EMAIL,
        password_hash=hash_password(_TEST_PASSWORD),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="Login (DB-based user authentication)",
    responses={
        200: {
            "description": "Login success",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "user": {"id": "user_1", "username": "test@pangyopass.com"},
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
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> ApiResponse[LoginResponse]:
    """Authenticate user and return a token.

    Temporary flow:
    - query user by email from DB
    - verify password hash
    - issue JWT token on success
    """

    db_user = db.scalar(select(User).where(User.email == payload.username_or_email))
    if db_user is None:
        # Seed one local test account when no user exists yet.
        if payload.username_or_email == _TEST_EMAIL:
            db_user = _get_or_create_test_user(db)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTH_INVALID_CREDENTIALS,
            )

    if not verify_password(payload.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_CREDENTIALS,
        )

    settings = get_settings()
    access_token = create_access_token(
        subject=str(db_user.id),
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        expires_minutes=settings.access_token_expire_minutes,
        extra_claims={"email": db_user.email},
    )

    return ApiResponse(
        success=True,
        data=LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserPublic(id=str(db_user.id), username=db_user.email, created_at=db_user.created_at),
        ),
        message=MSG_LOGIN_SUCCESS,
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserPublic],
    summary="Get current user (temporary)",
    responses={
        200: {
            "description": "Current user",
            "content": {
                "application/json": {
                    "example": {"id": "user_1", "username": "test@pangyopass.com"}
                }
            },
        },
        401: {
            "description": "Invalid or missing token",
            "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
        },
    },
)
def me(current_user: UserPublic = Depends(get_current_user)) -> ApiResponse[UserPublic]:
    return ApiResponse(success=True, data=current_user, message=MSG_FETCH_SUCCESS)


@router.post(
    "/register",
    response_model=ApiResponse[RegisterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        201: {
            "description": "User created",
            "content": {
                "application/json": {
                    "example": {
                        "user": {"id": "2", "username": "new-user@pangyopass.com"},
                        "message": "User registered successfully",
                    }
                }
            },
        },
        409: {
            "description": "Email already exists",
            "content": {
                "application/json": {"example": {"detail": "Email already registered"}}
            },
        },
    },
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> ApiResponse[RegisterResponse]:
    """Create a new user account."""

    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AUTH_EMAIL_ALREADY_REGISTERED,
        )

    new_user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return ApiResponse(
        success=True,
        data=RegisterResponse(
            user=UserPublic(
                id=str(new_user.id),
                username=new_user.email,
                created_at=new_user.created_at,
            ),
            message=MSG_REGISTER_SUCCESS,
        ),
        message=MSG_REGISTER_SUCCESS,
    )

