"""Common response schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Unified JSON response envelope."""

    success: bool = Field(..., examples=[True])
    data: T | None = None
    message: str = Field(..., examples=["OK"])

