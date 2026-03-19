"""Auth domain schemas.

These schemas are designed to be stable for frontend integration and easy to
extend later (e.g., adding roles, profile fields, refresh tokens, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    """Public user fields safe to return to clients."""

    id: str = Field(..., examples=["user_123"])
    email: EmailStr = Field(..., examples=["test@pangyopass.com"])
    created_at: Optional[datetime] = Field(None, examples=["2026-03-19T12:34:56Z"])


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["test@pangyopass.com"])
    password: str = Field(..., min_length=1, examples=["password1234"])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"email": "test@pangyopass.com", "password": "password1234"},
            ]
        }
    }


class LoginResponse(BaseModel):
    access_token: str = Field(..., examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    token_type: Literal["bearer"] = Field("bearer", examples=["bearer"])
    user: Optional[UserPublic] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "user": {"id": "user_123", "email": "test@pangyopass.com"},
                }
            ]
        }
    }


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., examples=["new-user@pangyopass.com"])
    password: str = Field(..., min_length=8, examples=["StrongPassword123!"])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"email": "new-user@pangyopass.com", "password": "StrongPassword123!"}
            ]
        }
    }


class RegisterResponse(BaseModel):
    user: UserPublic
    message: str = Field("User registered successfully", examples=["User registered successfully"])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user": {"id": "1", "email": "new-user@pangyopass.com"},
                    "message": "User registered successfully",
                }
            ]
        }
    }

