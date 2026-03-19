"""Terms domain router.

This module starts with a simple search placeholder and can be expanded to
real DB-backed search + save/bookmark features.
"""

from fastapi import APIRouter, Query

router = APIRouter(
    prefix="/terms",
    tags=["terms"],
)


@router.get(
    "/search",
    summary="Search Pangyo terms (placeholder)",
    responses={
        200: {
            "description": "Search result placeholder",
            "content": {
                "application/json": {
                    "example": {
                        "keyword": "온보딩",
                        "items": [
                            {
                                "id": 1,
                                "term": "온보딩",
                                "meaning": "새로운 구성원이 조직과 업무에 적응하는 과정",
                            }
                        ],
                        "total": 1,
                    }
                }
            },
        }
    },
)
def search_terms(keyword: str = Query(..., min_length=1, description="Search keyword")) -> dict:
    """Placeholder search endpoint.

    Later this function will query DB/FTS and return ranked results.
    """

    dummy_items = [
        {
            "id": 1,
            "term": "온보딩",
            "meaning": "새로운 구성원이 조직과 업무에 적응하는 과정",
        },
        {
            "id": 2,
            "term": "데일리 스탠드업",
            "meaning": "매일 짧게 진행하는 진행 상황 공유 미팅",
        },
    ]

    filtered = [item for item in dummy_items if keyword.lower() in item["term"].lower()]

    return {
        "keyword": keyword,
        "items": filtered,
        "total": len(filtered),
    }

