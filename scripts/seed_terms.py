#!/usr/bin/env python3
"""판교어 사전 엑셀/CSV → SQLite `terms` 적재 CLI.

프로젝트 루트에서 실행:

    py scripts/seed_terms.py path/to/terms.xlsx

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="판교어 terms 테이블 시드 적재")
    parser.add_argument(
        "file",
        type=Path,
        help="엑셀(.xlsx, .xlsm) 또는 CSV(.csv) 경로",
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

    if not args.file.is_file():
        print(f"오류: 파일이 없습니다 — {args.file.resolve()}", file=sys.stderr)
        return 1

    if not args.no_ensure_schema:
        Base.metadata.create_all(bind=engine)

    session: Session = SessionLocal()
    try:
        stats = run_seed_from_path(session, args.file.resolve(), dry_run=args.dry_run)
    finally:
        session.close()

    print("— 시드 결과 —")
    print(f"  삽입:              {stats.inserted}")
    print(f"  스킵 (DB에 이미 있음): {stats.skipped_duplicate_db}")
    print(f"  스킵 (파일 내 중복):   {stats.skipped_duplicate_file}")
    print(f"  스킵 (용어 비움):      {stats.skipped_empty_term}")
    print(f"  스킵 (필수값 누락):    {stats.skipped_invalid_row}")
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
