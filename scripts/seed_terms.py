#!/usr/bin/env python3
"""판교어 사전 엑셀/CSV → SQLite `terms` 적재 CLI.

프로젝트 루트에서 실행:

    python scripts/seed_terms.py
    python scripts/seed_terms.py data/pangyo_terms.csv

기본 파일: `data/pangyo_terms.csv` (경로 생략 시)

사전 준비:

    python -m pip install -r requirements-seed.txt

환경 변수 `PP_DATABASE_URL`로 DB 경로를 바꿀 수 있습니다 (기본: sqlite:///./pangyopass.db).
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

# 프로젝트 루트 (다른 디렉터리에서 실행해도 import 되도록 맨 위에서 고정)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "pangyo_terms.csv"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_PREFIX = "[seed]"


def _log_info(msg: str) -> None:
    print(f"{_PREFIX} {msg}", flush=True)


def _log_warn(msg: str) -> None:
    print(f"{_PREFIX} WARN  {msg}", file=sys.stderr, flush=True)


def _log_error(msg: str) -> None:
    print(f"{_PREFIX} ERROR {msg}", file=sys.stderr, flush=True)


def _log_success(msg: str) -> None:
    print(f"{_PREFIX} OK    {msg}", flush=True)


def _parse_args() -> argparse.Namespace:
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
        help="DB에 쓰지 않고 삽입될 건만 계산",
    )
    parser.add_argument(
        "--no-ensure-schema",
        action="store_true",
        help="create_all(테이블 자동 생성) 생략",
    )
    return parser.parse_args()


def main() -> int:
    """CLI 진입점. 성공 시 0, 실패 시 1 (사용자 중단 130)."""
    args = _parse_args()

    try:
        return _run_seed(args)
    except KeyboardInterrupt:
        _log_error("사용자에 의해 중단되었습니다.")
        return 130


def _run_seed(args: argparse.Namespace) -> int:
    """DB 세션을 열고 시드를 수행한다. 예외는 잡아 메시지와 함께 종료 코드를 반환한다."""
    try:
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm import Session

        from app.core.config import get_settings
        from db.base import Base
        from db.seed.loader import run_seed_from_path
        from db.session import SessionLocal, engine
    except ModuleNotFoundError as e:
        _log_error(
            "필요한 패키지가 없습니다. 프로젝트 루트에서 다음을 실행하세요:\n"
            "  python -m pip install -r requirements-seed.txt\n"
            f"  (원인: {e})"
        )
        return 1

    csv_path = args.file.resolve()
    if not csv_path.is_file():
        _log_error(f"파일을 찾을 수 없습니다: {csv_path}")
        return 1

    settings = get_settings()
    _log_info(f"작업 디렉터리 기준 ROOT: {ROOT}")
    _log_info(f"입력 파일: {csv_path}")
    _log_info(f"데이터베이스: {settings.database_url}")
    if args.dry_run:
        _log_info("모드: dry-run (커밋 없음)")

    session: Session = SessionLocal()
    stats = None
    try:
        if not args.no_ensure_schema:
            _log_info("스키마 확인 중 (create_all)…")
            Base.metadata.create_all(bind=engine)

        _log_info("시드 적재 시작…")
        stats = run_seed_from_path(session, csv_path, dry_run=args.dry_run)
    except (SQLAlchemyError, OSError, ValueError) as e:
        session.rollback()
        _log_error(f"시드 적재 실패: {e}")
        traceback.print_exc(file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — CLI에서 마지막 방어선
        session.rollback()
        _log_error(f"예기치 않은 오류: {e}")
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        session.close()
        _log_info("DB 세션이 종료되었습니다.")

    if stats is None:
        _log_error("통계 정보를 가져오지 못했습니다.")
        return 1

    print()
    print("────────── 시드 결과 ──────────")
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
        print()
        print("────────── 경고 (일부) ──────────")
        for w in stats.warnings[:50]:
            _log_warn(w)
        if len(stats.warnings) > 50:
            _log_warn(f"... 외 {len(stats.warnings) - 50}건")

    _log_success(
        f"완료 — 삽입 {stats.inserted}건, 스킵 {stats.skipped_total}건"
        + (" [dry-run]" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
