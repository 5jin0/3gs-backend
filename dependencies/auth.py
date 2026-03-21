"""Authentication dependencies.

This module centralizes token extraction & validation so all endpoints can reuse
the same authentication logic via Depends().
"""

from __future__ import annotations

from typing import Any

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


def _decode_access_token_payload(
    credentials: HTTPAuthorizationCredentials | None,
) -> dict[str, Any]:
    """Bearer 토큰을 검증하고 JWT 페이로드를 반환합니다. 실패 시 401."""

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )

    settings = get_settings()
    try:
        return decode_token(
            token=credentials.credentials,
            secret_key=settings.secret_key,
            algorithm=settings.algorithm,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserPublic:
    """Validate access token and return current user from JWT claims (no DB read).

    구형 토큰·일부 엔드포인트 호환용. ``is_admin`` 등은 발급 시점 클레임 기준입니다.
    프로필 동기화가 필요하면 :func:`get_current_user_from_db` / ``GET /auth/me`` 를 사용하세요.
    """

    payload = _decode_access_token_payload(credentials)

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )

    raw_admin = payload.get("is_admin")
    is_admin = bool(raw_admin) if raw_admin is not None else False

    return UserPublic(
        id=str(user_id),
        username=str(email),
        is_admin=is_admin,
    )


def get_current_user_from_db(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> UserPublic:
    """Bearer 검증 후 DB에서 사용자를 읽어 반환합니다.

    ``is_admin``·이메일·``created_at`` 은 DB 기준이며 JWT 클레임보다 우선합니다.
    토큰의 ``sub`` 로 사용자를 찾지 못하면 401입니다.
    """

    payload = _decode_access_token_payload(credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )
    try:
        uid = int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MSG_INVALID_USER_TOKEN_SUBJECT,
        ) from exc

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )

    return UserPublic(
        id=str(user.id),
        username=user.email,
        created_at=user.created_at,
        is_admin=bool(user.is_admin),
    )


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> UserPublic:
    """인증된 사용자이면서 DB상 관리자인 경우에만 통과합니다.

    JWT의 ``is_admin`` 클레임이 아니라 DB ``users.is_admin`` 만 사용합니다.
    ``sub`` 만 있으면 되며 ``email`` 클레임은 필요하지 않습니다.
    """

    payload = _decode_access_token_payload(credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_NOT_AUTHENTICATED,
        )
    try:
        uid = int(user_id)
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
