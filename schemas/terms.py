"""Terms domain schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TermSearchItem(BaseModel):
    """검색 결과 한 건. JSON에는 original_meaning → originalMeaning 으로 직렬화."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., examples=[1])
    term: str = Field(..., examples=["온보딩"])
    # CSV "뜻" → DB definition (프론트 정의/요약 표시용 기존 필드명 유지)
    meaning: str = Field(..., examples=["새로운 구성원이 조직과 업무에 적응하는 과정"])
    # CSV "원래 의미" / "사용 예시"
    original_meaning: str = Field(
        default="",
        serialization_alias="originalMeaning",
        examples=["Onboarding"],
    )
    example: str = Field(default="", examples=["신입 온보딩 주간을 진행한다."])


class TermSearchResponse(BaseModel):
    keyword: str = Field(..., examples=["온보딩"])
    items: list[TermSearchItem] = Field(default_factory=list)
    total: int = Field(0, examples=[0, 2])


class TermSuggestionItem(BaseModel):
    term: str = Field(..., examples=["깃타"])


class TermSaveRequest(BaseModel):
    """Save one term to the authenticated user's wordbook."""

    model_config = ConfigDict(populate_by_name=True)

    # Accept both `term_id` and camelCase `termId` from clients.
    term_id: int = Field(
        ...,
        gt=0,
        validation_alias="termId",
        serialization_alias="term_id",
        examples=[42],
    )


class TermSaveResponse(BaseModel):
    """Result of a wordbook save (new row or existing duplicate)."""

    saved_id: int = Field(..., description="Primary key of saved_terms row", examples=[1])
    term_id: int = Field(..., examples=[42])
    user_id: int = Field(..., examples=[1])
    already_saved: bool = Field(
        False,
        description="True when this user had already saved this term",
        examples=[False],
    )


class TermWordbookRemoveResponse(BaseModel):
    """Result of removing a term from the wordbook (DELETE /wordbook/{term_id})."""

    term_id: int = Field(..., description="Term.id that was targeted", examples=[42])
    removed: bool = Field(
        ...,
        description="True if a saved_terms row existed and was deleted",
        examples=[True],
    )


class SavedTermItem(BaseModel):
    """One row in the logged-in user's wordbook (joined SavedTerm + Term)."""

    model_config = ConfigDict(populate_by_name=True)

    term_id: int = Field(
        ...,
        description="Primary key of the Term (NOT the saved_terms row id)",
        examples=[1],
    )
    term: str = Field(..., examples=["온보딩"])
    original_meaning: str = Field(
        default="",
        serialization_alias="originalMeaning",
        examples=["Onboarding"],
    )
    definition: str = Field(
        ...,
        examples=["새로운 구성원이 조직과 업무에 적응하는 과정"],
    )
    example: str = Field(default="", examples=["신입 온보딩 주간을 진행한다."])
    saved_at: datetime | None = Field(
        None,
        description="When the user saved this term (saved_terms.created_at)",
        examples=["2026-03-19T12:34:56Z"],
    )

