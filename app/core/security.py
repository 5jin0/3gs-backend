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


def decode_token(*, token: str, secret_key: str, algorithm: str) -> Dict[str, Any]:
    """Decode and validate a JWT token.

    Raises jose exceptions on invalid/expired tokens.
    """

    return jwt.decode(token, secret_key, algorithms=[algorithm])

