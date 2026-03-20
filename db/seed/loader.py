"""판교어 사전 엑셀/CSV → `terms` 테이블 적재.

엑셀 헤더(정확히 일치):
    용어, 원래 의미, 뜻, 사용 예시

중복 `term`(용어 문자열, strip 후)은 DB에 이미 있거나
같은 파일 안에서 이미 삽입한 경우 스킵합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.term import Term


# 엑셀/CSV 한글 헤더 → Term 필드
COLUMN_TERM = "용어"
COLUMN_ORIGINAL = "원래 의미"
COLUMN_DEFINITION = "뜻"
COLUMN_EXAMPLE = "사용 예시"

REQUIRED_COLUMNS = [COLUMN_TERM, COLUMN_ORIGINAL, COLUMN_DEFINITION, COLUMN_EXAMPLE]


@dataclass
class SeedStats:
    """적재 결과 집계."""

    inserted: int = 0
    skipped_duplicate_db: int = 0
    skipped_duplicate_file: int = 0
    skipped_empty_term: int = 0
    skipped_invalid_row: int = 0
    warnings: list[str] = field(default_factory=list)


def read_terms_file(path: Path) -> pd.DataFrame:
    """확장자에 따라 엑셀 또는 CSV를 읽어 DataFrame으로 반환."""

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(path, engine="openpyxl")
    if suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    raise ValueError(
        f"지원하지 않는 파일 형식입니다: {suffix}. "
        "사용 가능: .xlsx, .xlsm, .csv (구형 .xls는 엑셀에서 .xlsx로 저장해 주세요)"
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"필수 컬럼이 없습니다: {missing}. "
            f"현재 컬럼: {list(df.columns)}. "
            f"필요: {REQUIRED_COLUMNS}"
        )
    return df


def _cell_str(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def seed_terms_from_dataframe(db: Session, df: pd.DataFrame, *, dry_run: bool = False) -> SeedStats:
    """DataFrame을 검증한 뒤 `terms`에 삽입 (중복 term 스킵)."""

    df = _normalize_columns(df)
    stats = SeedStats()

    existing: set[str] = set(db.scalars(select(Term.term)).all())
    seen_in_file: set[str] = set()

    to_add: list[Term] = []

    for idx, row in df.iterrows():
        term = _cell_str(row[COLUMN_TERM])
        if not term:
            stats.skipped_empty_term += 1
            stats.warnings.append(f"행 {idx}: 용어가 비어 있어 스킵")
            continue

        original_meaning = _cell_str(row[COLUMN_ORIGINAL])
        definition = _cell_str(row[COLUMN_DEFINITION])
        example = _cell_str(row[COLUMN_EXAMPLE])

        if not original_meaning or not definition:
            stats.skipped_invalid_row += 1
            stats.warnings.append(
                f"행 {idx} (용어={term!r}): 원래 의미 또는 뜻이 비어 있어 스킵"
            )
            continue

        if term in existing:
            stats.skipped_duplicate_db += 1
            continue
        if term in seen_in_file:
            stats.skipped_duplicate_file += 1
            stats.warnings.append(f"행 {idx}: 파일 내 중복 용어 스킵 — {term!r}")
            continue

        seen_in_file.add(term)
        to_add.append(
            Term(
                term=term,
                original_meaning=original_meaning,
                definition=definition,
                example=example,
            )
        )

    if dry_run:
        stats.inserted = len(to_add)
        return stats

    for obj in to_add:
        db.add(obj)
    db.commit()

    stats.inserted = len(to_add)
    for t in to_add:
        existing.add(t.term)

    return stats


def run_seed_from_path(
    db: Session,
    file_path: Path,
    *,
    dry_run: bool = False,
) -> SeedStats:
    """파일 경로에서 읽어 적재까지 수행."""

    df = read_terms_file(file_path)
    return seed_terms_from_dataframe(db, df, dry_run=dry_run)
