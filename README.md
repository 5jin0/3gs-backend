# PangyoPass Backend (FastAPI)

판교패스(PangyoPass) 서비스의 백엔드 API 서버입니다.  
프론트엔드(Next.js)에서 호출하는 REST API를 제공하며, 현재는 빠른 연동을 위해 SQLite + 일부 더미 응답 기반으로 구성되어 있습니다.

## 기술 스택

- Python + FastAPI
- SQLAlchemy (SQLite 기본)
- Pydantic (요청/응답 스키마)
- JWT (`python-jose`) + bcrypt/passlib (인증 확장 기반)

## 실행 방법

```bash
# 1) 가상환경 생성
py -m venv .venv

# 2) 가상환경 활성화 (PowerShell)
.venv\Scripts\Activate.ps1

# 3) 패키지 설치
pip install -r requirements.txt

# 4) 개발 서버 실행
uvicorn app.main:app --reload
```

서버 실행 후 Swagger UI:

- http://127.0.0.1:8000/docs

## 환경 변수

기본 설정은 `app/core/config.py`에 있으며, `PP_` prefix 환경변수로 덮어쓸 수 있습니다.

주요 변수:

- `PP_APP_NAME` (기본: `PangyoPass API`)
- `PP_ENVIRONMENT` (기본: `local`)
- `PP_CORS_ORIGINS` (기본: `["http://localhost:3000"]`)
- `PP_DATABASE_URL` (기본: `sqlite:///./pangyopass.db`)
- `PP_DB_ECHO` (기본: `False`)
- `PP_SECRET_KEY` (기본: `CHANGE_ME`)
- `PP_ALGORITHM` (기본: `HS256`)
- `PP_ACCESS_TOKEN_EXPIRE_MINUTES` (기본: `60`)

## 폴더 구조

```text
app/
  main.py                 # FastAPI 엔트리포인트
  core/
    config.py             # 환경설정
    security.py           # JWT/비밀번호 해시 유틸
    messages.py           # 공통 메시지 상수

routers/
  api.py                  # 루트(/) 라우터
  health.py               # /health
  auth.py                 # /auth/*
  terms.py                # /terms/*

schemas/
  common.py               # 공통 응답 래퍼 (success/data/message)
  auth.py                 # 인증 요청/응답 스키마
  terms.py                # terms 요청/응답 스키마

dependencies/
  auth.py                 # 인증 dependency (get_current_user)
  db.py                   # DB dependency (get_db)

db/
  base.py                 # SQLAlchemy Declarative Base
  session.py              # engine/session/get_db
  seed/                   # 엑셀/CSV → terms 적재 로직 및 문서
  models/
    user.py               # User 모델
    term.py               # Term 모델
    saved_term.py         # SavedTerm(북마크) 모델

scripts/
  seed_terms.py           # 판교어 사전 시드 CLI
```

## 용어(판교어) 시드 적재

엑셀/CSV를 `terms` 테이블에 넣으려면:

```powershell
py -m pip install -r requirements-seed.txt
# 기본 CSV: data/pangyo_terms.csv
py scripts/seed_terms.py
py scripts/seed_terms.py .\path\to\terms.xlsx
```

상세 컬럼 매핑·`--dry-run`·환경 변수 설명은 [`db/seed/README.md`](db/seed/README.md)를 참고하세요.

## API 응답 형식

대부분의 성공 응답은 아래 공통 구조를 사용합니다.

```json
{
  "success": true,
  "data": {},
  "message": "..."
}
```

인증 실패/검증 실패 등은 FastAPI 기본 에러 형식(`detail`)을 사용합니다.

## 주요 API 목록

### 공통

- `GET /`
- `GET /health`

### 인증 (`/auth`)

- `POST /auth/register` : 회원가입
- `POST /auth/login` : 로그인(JWT 발급)
- `GET /auth/me` : 현재 로그인 사용자 조회 (Bearer Token)

### 용어 (`/terms`)

- `GET /terms/search?keyword=...` : 판교어 검색 (현재 더미)
- `GET /terms/saved` : 사용자 저장 단어 목록 조회

## 인증 방식 요약

- 로그인 성공 시 `access_token`(JWT) 발급
- 보호 API 호출 시 헤더에 Bearer Token 전달
  - `Authorization: Bearer <access_token>`
- 인증 검증은 `dependencies/auth.py`의 `get_current_user`에서 처리

## DB 스키마 보강 (기존 `pangyopass.db` 사용 시)

새 컬럼이 모델에만 추가되고 `create_all`은 기존 테이블을 **수정하지 않습니다.**  
이미 `users` 테이블이 있는 로컬 DB에는 아래처럼 **수동으로 컬럼을 추가**해야 할 수 있습니다.

예: `users.is_admin` (관리자 여부, SQLite)

```sql
ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;
```

- `0` = 일반 사용자, `1` = 관리자(추후 `/admin` API에서 사용 예정)
- 새로 DB 파일을 비우고 다시 띄우면 `create_all`로 테이블이 새로 만들어지면서 컬럼이 포함됩니다.

## 현재 구현 상태 및 참고

- DB는 SQLite 기본 (`pangyopass.db`)
- `POST /auth/login`은 개발 편의를 위해 테스트 계정(`test@pangyopass.com`) 자동 시드 로직 포함
- 검색 API는 더미 데이터 기반

## 추후 확장 예정

- `POST /terms/save` 저장 API
- 북마크/용어 CRUD 고도화
- Refresh Token 구조
- Alembic 마이그레이션 도입
- 예외 처리 전역 핸들러 고도화
