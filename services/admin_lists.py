"""관리자 목록·개요 조회."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from db.models.saved_term import SavedTerm
from db.models.term import Term
from db.models.user import User
from schemas.admin import (
    AdminOverview,
    AdminSaveListItem,
    AdminSaveListResult,
    AdminTermListItem,
    AdminTermListResult,
    AdminUserListItem,
    AdminUserListResult,
)


def _count_table(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def build_admin_overview(db: Session) -> AdminOverview:
    now = datetime.now(timezone.utc)
    return AdminOverview(
        user_count=_count_table(db, User),
        term_count=_count_table(db, Term),
        saved_term_count=_count_table(db, SavedTerm),
        generated_at_utc=now,
    )


def list_admin_users(db: Session, *, offset: int, limit: int) -> AdminUserListResult:
    total = _count_table(db, User)
    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    items = [
        AdminUserListItem(
            id=str(u.id),
            email=u.email,
            username=u.email,
            is_admin=bool(u.is_admin),
            created_at=u.created_at,
        )
        for u in rows
    ]
    return AdminUserListResult(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )


def list_admin_terms(db: Session, *, offset: int, limit: int) -> AdminTermListResult:
    total = _count_table(db, Term)
    stmt = select(Term).order_by(Term.id.asc()).offset(offset).limit(limit)
    rows = db.scalars(stmt).all()
    items = [
        AdminTermListItem(
            id=t.id,
            term=t.term,
            meaning=t.definition,
            original_meaning=t.original_meaning,
            example=t.example,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in rows
    ]
    return AdminTermListResult(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )


def list_admin_saves(db: Session, *, offset: int, limit: int) -> AdminSaveListResult:
    total = _count_table(db, SavedTerm)
    stmt = (
        select(SavedTerm)
        .options(joinedload(SavedTerm.term))
        .order_by(SavedTerm.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(stmt).unique().all()
    items: list[AdminSaveListItem] = []
    for st in rows:
        term_row = st.term
        term_label = term_row.term if term_row is not None else ""
        items.append(
            AdminSaveListItem(
                id=st.id,
                user_id=st.user_id,
                term_id=st.term_id,
                term=term_label,
                saved_at=st.created_at,
            )
        )
    return AdminSaveListResult(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )
