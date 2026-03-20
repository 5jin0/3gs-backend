"""User wordbook (saved terms) API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.messages import (
    MSG_INVALID_USER_TOKEN_SUBJECT,
    MSG_SAVED_TERMS_FETCHED,
    MSG_TERM_ALREADY_SAVED,
    MSG_TERM_NOT_FOUND,
    MSG_TERM_NOT_IN_WORDBOOK,
    MSG_TERM_REMOVED_FROM_WORDBOOK,
    MSG_TERM_SAVED,
)
from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.models.saved_term import SavedTerm
from db.models.term import Term
from db.models.user_access_event import UserAccessEvent
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from schemas.terms import SavedTermItem, TermSaveRequest, TermSaveResponse, TermWordbookRemoveResponse

router = APIRouter(
    prefix="/wordbook",
    tags=["wordbook"],
)
logger = logging.getLogger(__name__)


def _log_wordbook_view_event(db: Session, *, user_id: int) -> None:
    """Best-effort logging for wordbook view events."""

    try:
        # Ensure availability for older local DB files.
        from db.base import Base

        Base.metadata.create_all(bind=db.get_bind(), tables=[UserAccessEvent.__table__])
        db.add(UserAccessEvent(user_id=user_id, event_type="wordbook_view"))
        db.commit()
        logger.info("wordbook.view_event saved user_id=%s", user_id)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("wordbook.view_event save failed user_id=%s error=%s", user_id, exc)


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
    """Compatibility route for frontend calls to POST /wordbook/save."""

    logger.info(
        "wordbook.save received term_id=%s current_user_id=%s",
        body.term_id,
        current_user.id,
    )

    try:
        user_id = int(current_user.id)
    except ValueError:
        logger.warning("wordbook.save invalid current_user.id=%r", current_user.id)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message=MSG_INVALID_USER_TOKEN_SUBJECT,
            ).model_dump(mode="json"),
        )

    term = db.get(Term, body.term_id)
    if term is None:
        logger.info("wordbook.save term not found term_id=%s", body.term_id)
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
        user_saved_count = db.scalar(
            select(func.count(SavedTerm.id)).where(SavedTerm.user_id == user_id)
        ) or 0
        logger.info(
            "wordbook.save duplicate user_id=%s term_id=%s total_saved_rows=%s",
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
        user_saved_count = db.scalar(
            select(func.count(SavedTerm.id)).where(SavedTerm.user_id == user_id)
        ) or 0
        logger.info(
            "wordbook.save duplicate after race user_id=%s term_id=%s total_saved_rows=%s",
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
        logger.exception("wordbook.save commit failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[TermSaveResponse](
                success=False,
                data=None,
                message="Failed to save term",
            ).model_dump(mode="json"),
        )

    user_saved_count = db.scalar(
        select(func.count(SavedTerm.id)).where(SavedTerm.user_id == user_id)
    ) or 0
    logger.info(
        "wordbook.save success user_id=%s term_id=%s saved_id=%s total_saved_rows=%s",
        user_id,
        body.term_id,
        saved.id,
        user_saved_count,
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
    "",
    response_model=ApiResponse[list[SavedTermItem]],
    summary="Get current user's saved terms (wordbook)",
)
def get_wordbook_terms(
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[SavedTermItem]]:
    """Return current user's saved terms ordered by most recent save."""

    try:
        user_id = int(current_user.id)
    except ValueError:
        return ApiResponse(success=True, data=[], message=MSG_SAVED_TERMS_FETCHED)

    _log_wordbook_view_event(db, user_id=user_id)

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
    return ApiResponse(success=True, data=items, message=MSG_SAVED_TERMS_FETCHED)


@router.delete(
    "/{term_id}",
    response_model=ApiResponse[TermWordbookRemoveResponse],
    summary="Remove a term from the current user's wordbook",
)
def remove_saved_term(
    term_id: int = Path(..., ge=1, description="Term primary key (same as POST /terms/save)"),
    current_user: UserPublic = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[TermWordbookRemoveResponse] | JSONResponse:
    """Delete the SavedTerm row for (current user, term_id) if it exists."""

    try:
        user_id = int(current_user.id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiResponse[TermWordbookRemoveResponse](
                success=False,
                data=None,
                message=MSG_INVALID_USER_TOKEN_SUBJECT,
            ).model_dump(mode="json"),
        )

    saved = db.execute(
        select(SavedTerm).where(
            SavedTerm.user_id == user_id,
            SavedTerm.term_id == term_id,
        )
    ).scalar_one_or_none()

    if saved is None:
        return ApiResponse(
            success=False,
            data=TermWordbookRemoveResponse(term_id=term_id, removed=False),
            message=MSG_TERM_NOT_IN_WORDBOOK,
        )

    db.delete(saved)
    db.commit()

    return ApiResponse(
        success=True,
        data=TermWordbookRemoveResponse(term_id=term_id, removed=True),
        message=MSG_TERM_REMOVED_FROM_WORDBOOK,
    )
