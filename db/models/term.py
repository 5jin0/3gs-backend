"""용어(판교어) 사전 엔트리 — MVP 단일 테이블.

엑셀 컬럼 매핑 (시드 시 그대로 옮기면 됨):
    용어          -> term
    원래 의미      -> original_meaning
    뜻            -> definition
    사용 예시      -> example

MVP에 단일 테이블이 적합한 이유:
    - 조회·검색 API에서 한 row로 응답을 만들 수 있어 JOIN이 없다.
    - 엑셀 구조와 1:1이라 seed 스크립트가 단순하다.
    - 나중에 출처/태그/버전이 필요하면 TermSource, TermTag 같은 테이블로
      분리·정규화하면 되고, 지금은 과설계를 피한다.

term 필드:
    - 등호/부분 검색(LIKE, FTS)에 쓰일 가능성이 높아 index=True.
    - 엑셀에 동일 표기가 여러 행으로 있을 수 있어 unique는 걸지 않는다.
      (사전을 "용어 문자열당 1행"으로 고정하면 이후 UniqueConstraint 추가 가능.)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.saved_term import SavedTerm


class Term(Base):
    """판교어 사전 1레코드 = 엑셀 1행."""

    __tablename__ = "terms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 검색·표시의 기준 키 (엑셀 "용어")
    term: Mapped[str] = mapped_column(String(500), index=True, nullable=False)

    # 엑셀 "원래 의미"
    original_meaning: Mapped[str] = mapped_column(Text, nullable=False)

    # 엑셀 "뜻"
    definition: Mapped[str] = mapped_column(Text, nullable=False)

    # 엑셀 "사용 예시" (없으면 빈 문자열)
    example: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="",
        insert_default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    saved_terms: Mapped[list["SavedTerm"]] = relationship(
        "SavedTerm",
        back_populates="term",
        cascade="all, delete-orphan",
    )
