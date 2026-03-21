"""Authentication-related endpoints (placeholder for now).

This router will host:
- POST /auth/login
- GET  /auth/me
- POST /auth/register (later)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.messages import (
    AUTH_EMAIL_ALREADY_REGISTERED,
    AUTH_INVALID_CREDENTIALS,
    MSG_FETCH_SUCCESS,
    MSG_LOGIN_SUCCESS,
    MSG_REGISTER_SUCCESS,
)
from app.core.security import create_jwt_access_token, hash_password, verify_password
from dependencies.auth import get_current_user_from_db
from dependencies.db import get_db
from db.base import Base
from db.models.user_access_event import UserAccessEvent
from db.models.user import User
from schemas.auth import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, UserPublic
from schemas.common import ApiResponse

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)
logger = logging.getLogger(__name__)

@router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="Login (DB-based user authentication)",
    description=(
        "성공 시 `data.user`에 `is_admin`(boolean)이 포함되며, "
        "DB의 `users.is_admin`과 동일한 값입니다."
    ),
    responses={
        200: {
            "description": "Login success",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "token_type": "bearer",
                            "user": {
                                "id": "1",
                                "username": "test@pangyopass.com",
                                "created_at": "2026-03-19T12:34:56Z",
                                "is_admin": False,
                            },
                        },
                        "message": "Login succeeded",
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

    `data.user.is_admin`은 DB `users.is_admin`과 동일하게 반환합니다.
    """

    db_user = db.scalar(select(User).where(User.email == payload.username_or_email))
    if db_user is None:
        # If user doesn't exist, create it using the provided password.
        # (Early integration-friendly behavior; later steps can restrict this.)
        db_user = User(
            email=payload.username_or_email,
            password_hash=hash_password(payload.password),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    else:
        # Existing user: verify provided password.
        if not verify_password(payload.password, db_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTH_INVALID_CREDENTIALS,
            )

    settings = get_settings()
    access_token = create_jwt_access_token(
        subject=str(db_user.id),
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        expires_minutes=settings.access_token_expire_minutes,
        extra_claims={
            "email": db_user.email,
            "is_admin": bool(db_user.is_admin),
        },
    )

    # Access-event logging must not break login flow.
    try:
        Base.metadata.create_all(bind=db.get_bind(), tables=[UserAccessEvent.__table__])
        db.add(UserAccessEvent(user_id=db_user.id, event_type="login_success"))
        db.commit()
        logger.info("auth.access_event saved user_id=%s event_type=login_success", db_user.id)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("auth.access_event save failed user_id=%s error=%s", db_user.id, exc)

    return ApiResponse(
        success=True,
        data=LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserPublic(
                id=str(db_user.id),
                username=db_user.email,
                created_at=db_user.created_at,
                is_admin=bool(db_user.is_admin),
            ),
        ),
        message=MSG_LOGIN_SUCCESS,
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserPublic],
    summary="현재 로그인 사용자 (DB 기준 프로필)",
    description=(
        "Bearer 토큰으로 인증합니다. "
        "`is_admin`·이메일(`username`)·`created_at` 은 **DB** 기준이며 JWT 클레임과 다를 수 있습니다. "
        "토큰 만료·위조·사용자 삭제 시 401입니다."
    ),
    responses={
        200: {
            "description": "Current user",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "id": "user_1",
                            "username": "test@pangyopass.com",
                            "created_at": "2026-03-19T12:34:56Z",
                            "is_admin": False,
                        },
                        "message": "Fetched successfully",
                    }
                }
            },
        },
        401: {
            "description": "Invalid or missing token",
            "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
        },
    },
)
def me(current_user: UserPublic = Depends(get_current_user_from_db)) -> ApiResponse[UserPublic]:
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
                        "user": {
                            "id": "2",
                            "username": "new-user@pangyopass.com",
                            "is_admin": False,
                        },
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
                is_admin=bool(new_user.is_admin),
            ),
            message=MSG_REGISTER_SUCCESS,
        ),
        message=MSG_REGISTER_SUCCESS,
    )

