"""User wordbook (saved terms) API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.messages import (
    MSG_INVALID_USER_TOKEN_SUBJECT,
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
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from schemas.terms import TermSaveRequest, TermSaveResponse, TermWordbookRemoveResponse

router = APIRouter(
    prefix="/wordbook",
    tags=["wordbook"],
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
    """Compatibility route for frontend calls to POST /wordbook/save."""

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
    except SQLAlchemyError:
        db.rollback()
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
            saved_id=saved.id,
            term_id=saved.term_id,
            user_id=saved.user_id,
            already_saved=False,
        ),
        message=MSG_TERM_SAVED,
    )


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
