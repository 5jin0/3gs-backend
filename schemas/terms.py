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


class SavedTermItem(BaseModel):
    term_id: int = Field(..., examples=[1])
    term: str = Field(..., examples=["온보딩"])
    meaning: str = Field(..., examples=["새로운 구성원이 조직과 업무에 적응하는 과정"])
    saved_at: datetime | None = Field(None, examples=["2026-03-19T12:34:56Z"])


class SavedTermsResponse(BaseModel):
    items: list[SavedTermItem] = Field(default_factory=list)
    total: int = Field(0, examples=[0, 3])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"items": [], "total": 0},
                {
                    "items": [
                        {
                            "term_id": 1,
                            "term": "온보딩",
                            "meaning": "새로운 구성원이 조직과 업무에 적응하는 과정",
                            "saved_at": "2026-03-19T12:34:56Z",
                        }
                    ],
                    "total": 1,
                },
            ]
        }
    }

