"""관리자 목록·개요 조회."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, asc, desc, func, select
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
    AdminUserSaveCountItem,
    AdminUserSaveCountResult,
)


def _count_table(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def list_user_save_counts(
    db: Session,
    *,
    offset: int,
    limit: int,
    saved_from: datetime | None,
    saved_to: datetime | None,
    sort: str = "save_count_desc",
) -> AdminUserSaveCountResult:
    """유저별 saved_terms 행 수. 기간 필터는 saved_terms.created_at 기준."""

    if saved_from is not None and saved_to is not None:
        sf, st = _ensure_utc(saved_from), _ensure_utc(saved_to)
        if sf > st:
            raise ValueError("saved_from must be on or before saved_to")

    allowed_sort = {
        "save_count_desc",
        "save_count_asc",
        "username_asc",
        "username_desc",
    }
    if sort not in allowed_sort:
        raise ValueError(
            f"sort must be one of {sorted(allowed_sort)}",
        )

    cond = []
    if saved_from is not None:
        cond.append(SavedTerm.created_at >= _ensure_utc(saved_from))
    if saved_to is not None:
        cond.append(SavedTerm.created_at <= _ensure_utc(saved_to))

    total_stmt = select(func.count(func.distinct(SavedTerm.user_id)))
    if cond:
        total_stmt = total_stmt.where(and_(*cond))
    total = int(db.scalar(total_stmt) or 0)

    inner_base = select(
        SavedTerm.user_id,
        func.count(SavedTerm.id).label("save_count"),
        func.min(SavedTerm.created_at).label("first_saved"),
        func.max(SavedTerm.created_at).label("last_saved"),
    )
    if cond:
        inner_base = inner_base.where(and_(*cond))
    inner_base = inner_base.group_by(SavedTerm.user_id)
    inner = inner_base.subquery()

    order_parts = []
    if sort == "save_count_desc":
        order_parts = [desc(inner.c.save_count)]
    elif sort == "save_count_asc":
        order_parts = [asc(inner.c.save_count)]
    elif sort == "username_asc":
        order_parts = [asc(User.email)]
    else:
        order_parts = [desc(User.email)]

    agg = (
        select(
            inner.c.user_id,
            inner.c.save_count,
            inner.c.first_saved,
            inner.c.last_saved,
            User.email,
        )
        .select_from(inner)
        .join(User, User.id == inner.c.user_id)
        .order_by(*order_parts)
        .offset(offset)
        .limit(limit)
    )

    rows = db.execute(agg).all()

    items: list[AdminUserSaveCountItem] = []
    for r in rows:
        uid = int(r[0])
        cnt = int(r[1])
        first_s = r[2]
        last_s = r[3]
        email = str(r[4]) if r[4] is not None else ""
        items.append(
            AdminUserSaveCountItem(
                user_id=uid,
                email=email,
                username=email,
                save_count=cnt,
                first_saved_at=first_s,
                last_saved_at=last_s,
            )
        )

    return AdminUserSaveCountResult(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        saved_from_utc=_ensure_utc(saved_from) if saved_from is not None else None,
        saved_to_utc=_ensure_utc(saved_to) if saved_to is not None else None,
        source_table="saved_terms",
    )
