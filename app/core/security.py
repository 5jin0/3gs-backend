"""Security utilities (JWT).

This module intentionally stays framework-agnostic so it can be reused from:
- routers (auth endpoints)
- dependencies (get_current_user)
- background tasks (later)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt

import bcrypt


def create_access_token(
    *,
    subject: str,
    secret_key: str,
    algorithm: str,
    expires_minutes: int,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token.

    - subject: user identifier (stored as `sub`)
    - expires_minutes: token lifetime in minutes
    - extra_claims: additional claims to embed in payload (optional)
    """

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)

    to_encode: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def create_jwt_access_token(
    *,
    subject: str,
    secret_key: str,
    algorithm: str,
    expires_minutes: int,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create an access token (JWT).

    This is a convenience wrapper to match the expected interface in step-wise
    development.
    """

    return create_access_token(
        subject=subject,
        secret_key=secret_key,
        algorithm=algorithm,
        expires_minutes=expires_minutes,
        extra_claims=extra_claims,
    )


def decode_token(*, token: str, secret_key: str, algorithm: str) -> Dict[str, Any]:
    """Decode and validate a JWT token.

    Raises jose exceptions on invalid/expired tokens.
    """

    return jwt.decode(token, secret_key, algorithms=[algorithm])


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Note: bcrypt limits input to 72 bytes. We deterministically truncate to
    72 bytes to avoid runtime crashes for long passwords.
    """

    password_bytes = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def hash_password(password: str) -> str:
    """Alias for `get_password_hash` (kept for step-wise compatibility)."""

    return get_password_hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against a bcrypt hash string."""

    plain_password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(plain_password_bytes, hashed_password.encode("utf-8"))

