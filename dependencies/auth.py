"""Authentication dependencies.

This module centralizes token extraction & validation so all endpoints can reuse
the same authentication logic via Depends().
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.config import get_settings
from app.core.security import decode_token
from schemas.auth import UserPublic

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserPublic:
    """Validate access token and return current user (temporary)."""

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
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
            detail="Not authenticated",
        )

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Temporary: in later steps, load from DB using user_id.
    return UserPublic(id=str(user_id), email=str(email))

