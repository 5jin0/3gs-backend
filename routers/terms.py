"""Terms domain router.

This module starts with a simple search placeholder and can be expanded to
real DB-backed search + save/bookmark features.
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.messages import (
    MSG_FETCH_SUCCESS,
    MSG_INVALID_USER_TOKEN_SUBJECT,
    MSG_SAVED_TERMS_FETCHED,
    MSG_TERM_ALREADY_SAVED,
    MSG_TERM_NOT_FOUND,
    MSG_TERM_SAVED,
)
from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.models.saved_term import SavedTerm
from db.models.term import Term
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from schemas.terms import (
    SavedTermItem,
    TermSaveRequest,
    TermSaveResponse,
    TermSearchItem,
    TermSearchResponse,
    TermSuggestionItem,
)

router = APIRouter(
    prefix="/terms",
    tags=["terms"],
)
logger = logging.getLogger(__name__)


@router.get(
    "/suggestions",
    response_model=ApiResponse[list[TermSuggestionItem]],
    summary="Autocomplete suggestions for Pangyo terms",
)
def suggest_terms(
    keyword: str = Query("", description="Prefix keyword for term suggestions"),
    limit: int = Query(10, ge=1, le=20, description="Maximum suggestions to return"),
    db: Session = Depends(get_db),
) -> ApiResponse[list[TermSuggestionItem]]:
    """Return lightweight prefix-matched term suggestions for autocomplete."""

    normalized = keyword.strip()
    if not normalized:
        return ApiResponse(
            success=True,
            data=[],
            message="Suggestions fetched successfully",
        )

    try:
        rows = db.execute(
            select(Term.term)
            .where(Term.term.ilike(f"{normalized}%"))
            .order_by(func.length(Term.term).asc(), Term.term.asc())
            .limit(limit)
        ).all()
        suggestions = [TermSuggestionItem(term=row[0]) for row in rows]
        return ApiResponse(
            success=True,
            data=suggestions,
            message="Suggestions fetched successfully",
        )
    except SQLAlchemyError as exc:
        # Legacy SQLite schema compatibility (`name` column on old terms table).
        logger.warning("terms.suggestions primary query failed: %s", exc)
        legacy_rows = db.execute(
            text(
                "SELECT name "
                "FROM terms "
                "WHERE lower(name) LIKE lower(:kw) "
                "ORDER BY length(name) ASC, name ASC "
                "LIMIT :limit"
            ),
            {"kw": f"{normalized}%", "limit": limit},
        ).all()
        suggestions = [TermSuggestionItem(term=row[0]) for row in legacy_rows]
        return ApiResponse(
            success=True,
            data=suggestions,
            message="Suggestions fetched successfully",
        )


@router.post(
    "/save",
    response_model=ApiResponse[TermSaveResponse],
    summary="Save a term to the current user's wordbook",
)
def save_term_to_wordbook(
    body: TermSaveRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[TermSaveResponse] | JSONResponse:
    """Persist a bookmark for (current user, term) if it does not already exist."""

    try:
        user_id = int(current_user.id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message=MSG_INVALID_USER_TOKEN_SUBJECT,
            ).model_dump(mode="json"),
        )

    if db.get(Term, body.term_id) is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message=MSG_TERM_NOT_FOUND,
            ).model_dump(mode="json"),
        )

    existing = db.execute(
        select(SavedTerm).where(
            SavedTerm.user_id == user_id,
            SavedTerm.term_id == body.term_id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        return ApiResponse(
            success=True,
            data=TermSaveResponse(
                saved_id=existing.id,
                term_id=existing.term_id,
                user_id=existing.user_id,
                already_saved=True,
            ),
            message=MSG_TERM_ALREADY_SAVED,
        )

    saved = SavedTerm(user_id=user_id, term_id=body.term_id)
    db.add(saved)
    try:
        db.commit()
        db.refresh(saved)
    except IntegrityError:
        db.rollback()
        dup = db.execute(
            select(SavedTerm).where(
                SavedTerm.user_id == user_id,
                SavedTerm.term_id == body.term_id,
            )
        ).scalar_one()
        return ApiResponse(
            success=True,
            data=TermSaveResponse(
                saved_id=dup.id,
                term_id=dup.term_id,
                user_id=dup.user_id,
                already_saved=True,
            ),
            message=MSG_TERM_ALREADY_SAVED,
        )

    return ApiResponse(
        success=True,
        data=TermSaveResponse(
            saved_id=saved.id,
            term_id=saved.term_id,
            user_id=saved.user_id,
            already_saved=False,
        ),
        message=MSG_TERM_SAVED,
    )


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
                                "originalMeaning": "Onboarding",
                                "example": "신입 온보딩 주간을 진행한다.",
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
                original_meaning=row.original_meaning,
                example=row.example or "",
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
                TermSearchItem(
                    id=row[0],
                    term=row[1],
                    meaning=row[2],
                    original_meaning="",
                    example="",
                )
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
    response_model=ApiResponse[list[SavedTermItem]],
    summary="Get current user's saved terms (wordbook)",
    responses={
        200: {
            "description": "Saved terms list (newest save first)",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": [
                            {
                                "term_id": 1,
                                "term": "온보딩",
                                "originalMeaning": "Onboarding",
                                "definition": "새로운 구성원이 조직과 업무에 적응하는 과정",
                                "example": "신입 온보딩 주간을 진행한다.",
                                "saved_at": "2026-03-19T12:34:56Z",
                            }
                        ],
                        "message": "Saved terms fetched successfully",
                    }
                }
            },
        }
    },
)
def get_saved_terms(
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[SavedTermItem]]:
    """Return saved terms for the authenticated user (efficient SavedTerm ⋈ Term join)."""

    try:
        user_id = int(current_user.id)
    except ValueError:
        # Backward compatibility for older non-numeric JWT subjects.
        return ApiResponse(
            success=True,
            data=[],
            message=MSG_SAVED_TERMS_FETCHED,
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
            original_meaning=term.original_meaning,
            definition=term.definition,
            example=term.example or "",
            saved_at=saved.created_at,
        )
        for saved, term in rows
    ]
    return ApiResponse(
        success=True,
        data=items,
        message=MSG_SAVED_TERMS_FETCHED,
    )

