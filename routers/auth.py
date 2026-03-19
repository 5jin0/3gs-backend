"""Authentication-related endpoints (placeholder for now).

This router will host:
- POST /auth/login
- GET  /auth/me
- POST /auth/register (later)
"""

from fastapi import APIRouter, HTTPException, status

from schemas.auth import LoginRequest, LoginResponse, UserPublic

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


# Temporary hard-coded account (no DB yet)
_TEST_USER_ID = "user_1"
_TEST_EMAIL = "test@pangyopass.com"
_TEST_PASSWORD = "password1234"


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login (temporary, hard-coded user)",
    responses={
        200: {
            "description": "Login success",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "test-access-token",
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
def login(payload: LoginRequest) -> LoginResponse:
    """Authenticate user and return a token.

    NOTE: This is a placeholder implementation for early frontend integration.
    We'll replace this with DB lookup + password hash verification + JWT later.
    """

    if payload.email != _TEST_EMAIL or payload.password != _TEST_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return LoginResponse(
        access_token="test-access-token",
        token_type="bearer",
        user=UserPublic(id=_TEST_USER_ID, email=_TEST_EMAIL),
    )

