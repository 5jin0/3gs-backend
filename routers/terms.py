"""Terms domain router.

This module starts with a simple search placeholder and can be expanded to
real DB-backed search + save/bookmark features.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.models.saved_term import SavedTerm
from db.models.term import Term
from schemas.auth import UserPublic
from schemas.terms import SavedTermItem, SavedTermsResponse

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


@router.get(
    "/saved",
    response_model=SavedTermsResponse,
    summary="Get current user's saved terms",
    responses={
        200: {
            "description": "Saved terms list",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "term_id": 1,
                                "term": "온보딩",
                                "meaning": "새로운 구성원이 조직과 업무에 적응하는 과정",
                                "saved_at": "2026-03-19T12:34:56Z",
                            }
                        ],
                        "total": 1,
                    }
                }
            },
        }
    },
)
def get_saved_terms(
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedTermsResponse:
    """Return saved terms for the authenticated user."""

    try:
        user_id = int(current_user.id)
    except ValueError:
        # Backward compatibility for older non-numeric test IDs.
        return SavedTermsResponse(items=[], total=0)

    rows = db.execute(
        select(SavedTerm, Term)
        .join(Term, Term.id == SavedTerm.term_id)
        .where(SavedTerm.user_id == user_id)
        .order_by(SavedTerm.created_at.desc())
    ).all()

    items = [
        SavedTermItem(
            term_id=term.id,
            term=term.name,
            meaning=term.meaning,
            saved_at=saved.created_at,
        )
        for saved, term in rows
    ]
    return SavedTermsResponse(items=items, total=len(items))

