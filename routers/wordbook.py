"""User wordbook (saved terms) API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.messages import (
    MSG_INVALID_USER_TOKEN_SUBJECT,
    MSG_TERM_NOT_IN_WORDBOOK,
    MSG_TERM_REMOVED_FROM_WORDBOOK,
)
from dependencies.auth import get_current_user
from dependencies.db import get_db
from db.models.saved_term import SavedTerm
from schemas.auth import UserPublic
from schemas.common import ApiResponse
from schemas.terms import TermWordbookRemoveResponse

router = APIRouter(
    prefix="/wordbook",
    tags=["wordbook"],
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
