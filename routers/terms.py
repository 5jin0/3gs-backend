"""Terms domain router.

This module starts with a simple search placeholder and can be expanded to
real DB-backed search + save/bookmark features.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.messages import (
    MSG_FETCH_SUCCESS,
    MSG_INVALID_USER_TOKEN_SUBJECT,
    MSG_SAVED_TERMS_FETCHED,
    MSG_SEARCH_CLICK_EVENT_SAVED,
    MSG_SEARCH_COMPLETE_EVENT_SAVED,
    MSG_SEARCH_EXIT_EVENT_SAVED,
    MSG_SEARCH_START_EVENT_SAVED,
    MSG_SUGGESTION_SELECT_EVENT_SAVED,
    MSG_TERM_ALREADY_SAVED,
    MSG_TERM_NOT_FOUND,
    MSG_TERM_SAVED,
)
from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.base import Base
from db.models.wordbook_counter import WordbookCounter
from db.models.wordbook_save_event import WordbookSaveEvent
from db.models.repeat_search_log import RepeatSearchLog
from db.models.saved_term import SavedTerm
from db.models.search_analytics_event import SearchAnalyticsEvent
from db.models.search_event import SearchEvent
from db.models.term import Term
from db.models.user_access_event import UserAccessEvent
from db.models.user import User
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from schemas.terms import (
    SearchEventRequest,
    SearchEventResponse,
    SearchLifecycleEventResponse,
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


def _resolve_user_id(current_user: UserPublic) -> int | None:
    try:
        return int(current_user.id)
    except ValueError:
        return None


def _ensure_wordbook_metric_tables(db: Session) -> None:
    Base.metadata.create_all(
        bind=db.get_bind(),
        tables=[WordbookSaveEvent.__table__, WordbookCounter.__table__, UserAccessEvent.__table__],
    )


def _increase_wordbook_counter(db: Session, *, user_id: int, field_name: str) -> None:
    counter = db.get(WordbookCounter, user_id)
    if counter is None:
        counter = WordbookCounter(user_id=user_id)
        db.add(counter)
        db.flush()
    setattr(counter, field_name, int(getattr(counter, field_name)) + 1)


def _compute_user_cohort(db: Session, *, user_id: int) -> str:
    user = db.get(User, user_id)
    if user is None or user.created_at is None:
        return "unknown"

    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return "new_user" if created >= datetime.now(timezone.utc) - timedelta(days=7) else "existing_user"


def _save_search_lifecycle_event(
    *,
    event_type: str,
    body: SearchEventRequest,
    current_user: UserPublic,
    db: Session,
) -> ApiResponse[SearchLifecycleEventResponse] | JSONResponse:
    Base.metadata.create_all(
        bind=db.get_bind(),
        tables=[SearchAnalyticsEvent.__table__, RepeatSearchLog.__table__],
    )

    user_id = _resolve_user_id(current_user)
    if user_id is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse[SearchLifecycleEventResponse](
                success=False,
                data=None,
                message=MSG_INVALID_USER_TOKEN_SUBJECT,
            ).model_dump(mode="json"),
        )

    keyword = body.keyword.strip()
    cohort = _compute_user_cohort(db, user_id=user_id)
    event = SearchAnalyticsEvent(
        user_id=user_id,
        event_type=event_type,
        cohort=cohort,
        keyword=keyword,
    )
    db.add(event)

    repeat_count: int | None = None
    if event_type == "search_complete":
        row = db.execute(
            select(RepeatSearchLog).where(
                RepeatSearchLog.user_id == user_id,
                RepeatSearchLog.keyword == keyword,
            )
        ).scalar_one_or_none()
        if row is None:
            row = RepeatSearchLog(user_id=user_id, keyword=keyword, repeat_count=1)
            db.add(row)
            repeat_count = 1
        else:
            row.repeat_count += 1
            repeat_count = row.repeat_count

    try:
        db.commit()
        db.refresh(event)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[SearchLifecycleEventResponse](
                success=False,
                data=None,
                message="Failed to save search lifecycle event",
            ).model_dump(mode="json"),
        )

    return ApiResponse(
        success=True,
        data=SearchLifecycleEventResponse(
            event_id=event.id,
            event_type=event.event_type,
            keyword=event.keyword,
            user_id=event.user_id,
            cohort=event.cohort,
            repeat_count=repeat_count,
        ),
        message=(
            MSG_SEARCH_COMPLETE_EVENT_SAVED
            if event_type == "search_complete"
            else MSG_SEARCH_EXIT_EVENT_SAVED
        ),
    )


def _log_search_event(
    *,
    event_type: str,
    body: SearchEventRequest,
    current_user: UserPublic,
    db: Session,
) -> ApiResponse[SearchEventResponse] | JSONResponse:
    """Persist one search interaction event for the authenticated user."""

    # Ensure new event table exists even when app runs with an older DB file.
    Base.metadata.create_all(bind=db.get_bind(), tables=[SearchEvent.__table__])

    try:
        user_id = int(current_user.id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse[SearchEventResponse](
                success=False,
                data=None,
                message=MSG_INVALID_USER_TOKEN_SUBJECT,
            ).model_dump(mode="json"),
        )

    keyword = body.keyword.strip()
    event = SearchEvent(user_id=user_id, event_type=event_type, keyword=keyword)
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[SearchEventResponse](
                success=False,
                data=None,
                message="Failed to save search event",
            ).model_dump(mode="json"),
        )

    return ApiResponse(
        success=True,
        data=SearchEventResponse(
            event_id=event.id,
            event_type=event.event_type,
            keyword=event.keyword,
            user_id=event.user_id,
        ),
        message=(
            MSG_SEARCH_START_EVENT_SAVED
            if event_type == "search_start"
            else (
                MSG_SEARCH_CLICK_EVENT_SAVED
                if event_type == "search_click"
                else MSG_SUGGESTION_SELECT_EVENT_SAVED
            )
        ),
    )


@router.post(
    "/events/search-start",
    response_model=ApiResponse[SearchEventResponse],
    summary="Save search-start event",
)
def save_search_start_event(
    body: SearchEventRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SearchEventResponse] | JSONResponse:
    return _log_search_event(
        event_type="search_start",
        body=body,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/events/search-click",
    response_model=ApiResponse[SearchEventResponse],
    summary="Save search-click event",
)
def save_search_click_event(
    body: SearchEventRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SearchEventResponse] | JSONResponse:
    return _log_search_event(
        event_type="search_click",
        body=body,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/events/suggestion-select",
    response_model=ApiResponse[SearchEventResponse],
    summary="Save suggestion-select event",
)
def save_suggestion_select_event(
    body: SearchEventRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SearchEventResponse] | JSONResponse:
    return _log_search_event(
        event_type="suggestion_select",
        body=body,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/events/search-complete",
    response_model=ApiResponse[SearchLifecycleEventResponse],
    summary="Save search-complete event and update repeat-search counter",
)
def save_search_complete_event(
    body: SearchEventRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SearchLifecycleEventResponse] | JSONResponse:
    return _save_search_lifecycle_event(
        event_type="search_complete",
        body=body,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/events/search-exit",
    response_model=ApiResponse[SearchLifecycleEventResponse],
    summary="Save search-exit event",
)
def save_search_exit_event(
    body: SearchEventRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SearchLifecycleEventResponse] | JSONResponse:
    return _save_search_lifecycle_event(
        event_type="search_exit",
        body=body,
        current_user=current_user,
        db=db,
    )


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

    logger.info(
        "terms.save received term_id=%s current_user_id=%s",
        body.term_id,
        current_user.id,
    )

    try:
        user_id = int(current_user.id)
    except ValueError:
        logger.warning("terms.save invalid current_user.id=%r", current_user.id)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message=MSG_INVALID_USER_TOKEN_SUBJECT,
            ).model_dump(mode="json"),
        )

    try:
        _ensure_wordbook_metric_tables(db)
        db.add(WordbookSaveEvent(user_id=user_id, term_id=body.term_id))
        _increase_wordbook_counter(db, user_id=user_id, field_name="save_click_count")
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("terms.save click-event save failed user_id=%s term_id=%s error=%s", user_id, body.term_id, exc)

    try:
        term_exists = db.get(Term, body.term_id) is not None
    except SQLAlchemyError as exc:
        logger.exception("terms.save failed term existence check: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message="Failed to validate term",
            ).model_dump(mode="json"),
        )

    if not term_exists:
        logger.info("terms.save term not found term_id=%s", body.term_id)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message=MSG_TERM_NOT_FOUND,
            ).model_dump(mode="json"),
        )

    try:
        existing = db.execute(
            select(SavedTerm).where(
                SavedTerm.user_id == user_id,
                SavedTerm.term_id == body.term_id,
            )
        ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        logger.exception("terms.save failed duplicate check: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message="Failed to check saved status",
            ).model_dump(mode="json"),
        )

    if existing is not None:
        logger.info(
            "terms.save already saved user_id=%s term_id=%s saved_id=%s",
            user_id,
            body.term_id,
            existing.id,
        )
        user_saved_count = db.scalar(
            select(func.count(SavedTerm.id)).where(SavedTerm.user_id == user_id)
        ) or 0
        logger.info(
            "terms.save duplicate found user_id=%s term_id=%s total_saved_rows=%s",
            user_id,
            body.term_id,
            user_saved_count,
        )
        return ApiResponse(
            success=True,
            data=TermSaveResponse(
                saved=False,
                already_saved=True,
                saved_id=existing.id,
                term_id=existing.term_id,
                user_id=existing.user_id,
            ),
            message=MSG_TERM_ALREADY_SAVED,
        )

    saved = SavedTerm(user_id=user_id, term_id=body.term_id)
    db.add(saved)
    try:
        _increase_wordbook_counter(db, user_id=user_id, field_name="save_success_count")
        db.commit()
        db.refresh(saved)
        logger.info(
            "terms.save success user_id=%s term_id=%s saved_id=%s",
            user_id,
            body.term_id,
            saved.id,
        )
        user_saved_count = db.scalar(
            select(func.count(SavedTerm.id)).where(SavedTerm.user_id == user_id)
        ) or 0
        logger.info(
            "terms.save commit succeeded user_id=%s term_id=%s total_saved_rows=%s",
            user_id,
            body.term_id,
            user_saved_count,
        )
    except IntegrityError:
        db.rollback()
        dup = db.execute(
            select(SavedTerm).where(
                SavedTerm.user_id == user_id,
                SavedTerm.term_id == body.term_id,
            )
        ).scalar_one()
        logger.info(
            "terms.save duplicate after race user_id=%s term_id=%s saved_id=%s",
            user_id,
            body.term_id,
            dup.id,
        )
        user_saved_count = db.scalar(
            select(func.count(SavedTerm.id)).where(SavedTerm.user_id == user_id)
        ) or 0
        logger.info(
            "terms.save race duplicate user_id=%s term_id=%s total_saved_rows=%s",
            user_id,
            body.term_id,
            user_saved_count,
        )
        return ApiResponse(
            success=True,
            data=TermSaveResponse(
                saved=False,
                already_saved=True,
                saved_id=dup.id,
                term_id=dup.term_id,
                user_id=dup.user_id,
            ),
            message=MSG_TERM_ALREADY_SAVED,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("terms.save commit failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message="Failed to save term",
            ).model_dump(mode="json"),
        )

    return ApiResponse(
        success=True,
        data=TermSaveResponse(
            saved=True,
            already_saved=False,
            saved_id=saved.id,
            term_id=saved.term_id,
            user_id=saved.user_id,
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

    try:
        _ensure_wordbook_metric_tables(db)
        db.add(UserAccessEvent(user_id=user_id, event_type="wordbook_view"))
        _increase_wordbook_counter(db, user_id=user_id, field_name="wordbook_view_count")
        db.commit()
        logger.info("terms.saved view_event saved user_id=%s", user_id)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("terms.saved view_event save failed user_id=%s error=%s", user_id, exc)

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

