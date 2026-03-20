"""Terms domain router.

This module starts with a simple search placeholder and can be expanded to
real DB-backed search + save/bookmark features.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.messages import MSG_FETCH_SUCCESS
from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.models.saved_term import SavedTerm
from db.models.term import Term
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from schemas.terms import SavedTermItem, SavedTermsResponse, TermSearchItem, TermSearchResponse

router = APIRouter(
    prefix="/terms",
    tags=["terms"],
)
logger = logging.getLogger(__name__)


@router.get(
    "/search",
    response_model=ApiResponse[TermSearchResponse],
    summary="Search Pangyo terms",
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
def search_terms(
    keyword: str = Query(..., min_length=1, description="Search keyword"),
    db: Session = Depends(get_db),
) -> ApiResponse[TermSearchResponse]:
    keyword = keyword.strip()
    try:
        total_terms = db.scalar(select(func.count(Term.id))) or 0
        logger.info("terms.search keyword=%r total_terms=%d", keyword, total_terms)

        rows = db.execute(
            select(Term)
            .where(Term.term.ilike(f"%{keyword}%"))
            .order_by(Term.id.asc())
        ).scalars().all()

        items = [
            TermSearchItem(
                id=row.id,
                term=row.term,
                meaning=row.definition,
            )
            for row in rows
        ]
        logger.info("terms.search matched_results=%d", len(items))
        payload = TermSearchResponse(keyword=keyword, items=items, total=len(items))
        return ApiResponse(success=True, data=payload, message=MSG_FETCH_SUCCESS)
    except SQLAlchemyError as exc:
        # Legacy SQLite schema compatibility:
        # older DBs may have `terms(name, meaning)` instead of new columns.
        logger.warning("terms.search primary query failed: %s", exc)
        try:
            legacy_total = db.execute(text("SELECT COUNT(*) FROM terms")).scalar_one()
            legacy_rows = db.execute(
                text(
                    "SELECT id, name, meaning "
                    "FROM terms "
                    "WHERE lower(name) LIKE lower(:kw) "
                    "ORDER BY id ASC"
                ),
                {"kw": f"%{keyword}%"},
            ).all()
            items = [
                TermSearchItem(id=row[0], term=row[1], meaning=row[2])
                for row in legacy_rows
            ]
            logger.info(
                "terms.search keyword=%r total_terms=%d matched_results=%d (legacy)",
                keyword,
                legacy_total,
                len(items),
            )
            payload = TermSearchResponse(keyword=keyword, items=items, total=len(items))
            return ApiResponse(success=True, data=payload, message=MSG_FETCH_SUCCESS)
        except SQLAlchemyError as legacy_exc:
            logger.error("terms.search legacy query failed: %s", legacy_exc)
            payload = TermSearchResponse(keyword=keyword, items=[], total=0)
            return ApiResponse(
                success=False,
                data=payload,
                message="Search failed due to database schema mismatch",
            )


@router.get(
    "/saved",
    response_model=ApiResponse[SavedTermsResponse],
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
) -> ApiResponse[SavedTermsResponse]:
    """Return saved terms for the authenticated user."""

    try:
        user_id = int(current_user.id)
    except ValueError:
        # Backward compatibility for older non-numeric test IDs.
        return ApiResponse(
            success=True,
            data=SavedTermsResponse(items=[], total=0),
            message=MSG_FETCH_SUCCESS,
        )

    rows = db.execute(
        select(SavedTerm, Term)
        .join(Term, Term.id == SavedTerm.term_id)
        .where(SavedTerm.user_id == user_id)
        .order_by(SavedTerm.created_at.desc())
    ).all()

    items = [
        SavedTermItem(
            term_id=term.id,
            term=term.term,
            # 목록에서는 엑셀 "뜻" 필드(definition)를 요약으로 노출
            meaning=term.definition,
            saved_at=saved.created_at,
        )
        for saved, term in rows
    ]
    return ApiResponse(
        success=True,
        data=SavedTermsResponse(items=items, total=len(items)),
        message=MSG_FETCH_SUCCESS,
    )

