"""Authentication dependencies.

This module centralizes token extraction & validation so all endpoints can reuse
the same authentication logic via Depends().
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.messages import (
    AUTH_ADMIN_REQUIRED,
    AUTH_NOT_AUTHENTICATED,
    MSG_INVALID_USER_TOKEN_SUBJECT,
)
from app.core.security import decode_token
from dependencies.db import get_db
from db.models.user import User
from schemas.auth import UserPublic

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserPublic:
    """Validate access token and return current user (temporary)."""

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )

    settings = get_settings()
    token = credentials.credentials

    try:
        payload = decode_token(
            token=token,
            secret_key=settings.secret_key,
            algorithm=settings.algorithm,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )

    # 구형 토큰에는 is_admin이 없을 수 있음 → False
    raw_admin = payload.get("is_admin")
    is_admin = bool(raw_admin) if raw_admin is not None else False

    # Temporary: in later steps, load from DB using user_id.
    return UserPublic(
        id=str(user_id),
        username=str(email),
        is_admin=is_admin,
    )


def require_admin(
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    """인증된 사용자이면서 DB상 관리자인 경우에만 통과합니다.

    JWT의 `is_admin`과 달리 DB 값을 기준으로 하므로, 승격/강등 후에도
    재로그인 없이는 이전 토큰으로 관리자 API를 쓸 수 없습니다.
    """

    try:
        uid = int(current_user.id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MSG_INVALID_USER_TOKEN_SUBJECT,
        ) from exc

    user = db.get(User, uid)
    if user is None or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AUTH_ADMIN_REQUIRED,
        )

    return UserPublic(
        id=str(user.id),
        username=user.email,
        created_at=user.created_at,
        is_admin=bool(user.is_admin),
    )

