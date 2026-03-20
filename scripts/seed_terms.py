#!/usr/bin/env python3
"""판교어 사전 엑셀/CSV → SQLite `terms` 적재 CLI.

프로젝트 루트에서 실행:

    py scripts/seed_terms.py
    py scripts/seed_terms.py data/pangyo_terms.csv

기본 파일: `data/pangyo_terms.csv` (경로 생략 시)

사전 준비:

    py -m pip install -r requirements-seed.txt

환경 변수 `PP_DATABASE_URL`로 DB 경로를 바꿀 수 있습니다 (기본: sqlite:///./pangyopass.db).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 import 경로에 추가
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "pangyo_terms.csv"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="판교어 terms 테이블 시드 적재")
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV,
        help=f"엑셀(.xlsx, .xlsm) 또는 CSV(.csv). 기본: {DEFAULT_CSV}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 쓰지 않고 삽입될 건수만 계산",
    )
    parser.add_argument(
        "--no-ensure-schema",
        action="store_true",
        help="DB 테이블 자동 생성(create_all) 생략",
    )
    args = parser.parse_args()

    # pandas/openpyxl — requirements-seed.txt (argparse 이후에만 로드, --help 시 불필요)
    from sqlalchemy.orm import Session

    from db.base import Base
    from db.seed.loader import run_seed_from_path
    from db.session import SessionLocal, engine

    csv_path = args.file.resolve()
    if not csv_path.is_file():
        print(f"오류: 파일이 없습니다 — {csv_path}", file=sys.stderr)
        return 1

    if not args.no_ensure_schema:
        Base.metadata.create_all(bind=engine)

    session: Session = SessionLocal()
    try:
        stats = run_seed_from_path(session, csv_path, dry_run=args.dry_run)
    finally:
        session.close()

    print("— 시드 결과 —")
    print(f"  CSV/파일 총 행 수:     {stats.total_rows}")
    print(f"  삽입된 행 수:          {stats.inserted}")
    print(f"  스킵된 행 수 (합계): {stats.skipped_total}")
    print("    └ 상세:")
    print(f"       DB 중복(term):      {stats.skipped_duplicate_db}")
    print(f"       파일 내 중복(term): {stats.skipped_duplicate_file}")
    print(f"       용어 비움:          {stats.skipped_empty_term}")
    print(f"       필수값 누락:        {stats.skipped_invalid_row}")
    if args.dry_run:
        print("  (dry-run: 실제 커밋 없음)")

    if stats.warnings:
        print("\n— 경고 (일부만 표시) —")
        for w in stats.warnings[:50]:
            print(f"  {w}")
        if len(stats.warnings) > 50:
            print(f"  ... 외 {len(stats.warnings) - 50}건")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
