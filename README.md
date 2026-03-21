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
  admin.py                # /admin/* (관리자 전용)
  terms.py                # /terms/*
  wordbook.py             # /wordbook/*

schemas/
  common.py               # 공통 응답 래퍼 (success/data/message)
  auth.py                 # 인증 요청/응답 스키마
  admin.py                # 관리자 응답 스키마
  terms.py                # terms 요청/응답 스키마

services/
  admin_metrics.py        # 관리자 대시보드 집계
  admin_lists.py          # 관리자 목록·개요 조회
  cohort_reaccess_metrics.py  # 코호트·재접속
  retention_metrics.py      # 리텐션 매트릭스
  search_funnel_metrics.py
  search_timing_metrics.py

dependencies/
  auth.py                 # get_current_user, require_admin
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
- `GET /auth/me` : 현재 로그인 사용자 조회 (Bearer). **`is_admin` 등은 DB 기준** (JWT보다 우선)

### 용어 (`/terms`)

- `GET /terms/search?keyword=...` : 판교어 검색 (현재 더미)
- `GET /terms/saved` : 사용자 저장 단어 목록 조회

### 관리자 (`/admin`)

DB에서 `users.is_admin = 1`인 계정만 접근 가능합니다. JWT의 `is_admin` 클레임이 아니라 **항상 DB 값**으로 검사합니다.

- `GET /admin/ping` : 관리자 권한·토큰 스모크 테스트
- `GET /admin/me` : 현재 관리자 사용자 정보(DB 기준)
- `GET /admin/overview` : 개요 카운트 (`user_count`, `term_count`, `saved_term_count`)
- `GET /admin/metrics/overview?recent_days=7` : 대시보드용 누적·최근 N일 집계
- `GET /admin/metrics/search-funnel?start=&end=` : 검색 퍼널·클릭률·자동완성·실패율 (`search_events` 기간 집계, UTC)
- `GET /admin/metrics/search-timing?start=&end=&session_gap_seconds=` : 클릭→입력·입력→이탈(인지부담) 시간 분포(초, p50/p90)
- `GET /admin/metrics/cohort-reaccess?start=&end=&cohort_mode=` : 로그인·접속 요약 + 가입 주차 또는 search_analytics cohort별 재접속률
- `GET /admin/metrics/retention?start=&end=&granularity=&max_periods=` : 가입 코호트별 리텐션(활성=`login_success`, 일·주·월)
- `GET /admin/users?offset=&limit=` : 사용자 목록
- `GET /admin/terms?offset=&limit=` : 용어 전체 목록 (검색 API와 맞는 필드 매핑)
- `GET /admin/saves?offset=&limit=` : 전 사용자 단어장 저장 이력

## 인증 방식 요약

- 로그인 성공 시 `access_token`(JWT) 발급
- 보호 API 호출 시 헤더에 Bearer Token 전달
  - `Authorization: Bearer <access_token>`
- 인증 검증은 `dependencies/auth.py`에서 처리합니다.  
  - 일부 API는 `get_current_user`(JWT 클레임만 사용, 구형 토큰 호환).  
  - **`GET /auth/me`는 `get_current_user_from_db`** 로 DB에서 사용자를 읽으며, **`is_admin`·이메일(`username`)·`created_at`은 DB 기준**입니다. JWT 클레임과 다를 수 있으니 **클라이언트는 `/auth/me`로 프로필을 동기화**하는 것을 권장합니다.
- `POST /auth/login` 응답의 `data.user.is_admin`은 **로그인 시점 DB**와 동일합니다.
- 관리자 API(`require_admin`)는 JWT의 `is_admin`이 아니라 **DB의 `is_admin`**만 봅니다. DB에서 승격하면 **같은 토큰으로도** 바로 `/admin/*`를 호출할 수 있습니다.

## 관리자 계정 만들기 · curl 예시

### 1) SQLite에서 특정 이메일을 관리자로 승격

[`sqlite3`](https://www.sqlite.org/cli.html) 또는 DB 브라우저에서 실행:

```sql
-- 이메일을 본인 환경에 맞게 수정
UPDATE users SET is_admin = 1 WHERE email = 'test@pangyopass.com';
```

되돌리기: `UPDATE users SET is_admin = 0 WHERE email = '...';`

`is_admin` 컬럼이 아직 없다면 아래 **「DB 스키마 보강 (기존 pangyopass.db 사용 시)」** 절의 `ALTER TABLE`을 먼저 적용하세요.

### 2) 로그인 후 토큰 받기 (PowerShell)

```powershell
$body = @{ username = "test@pangyopass.com"; password = "비밀번호" } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/auth/login" -Method Post -Body $body -ContentType "application/json"
$token = $r.data.access_token
```

### 3) 관리자 API 호출

```powershell
$h = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/ping" -Headers $h
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/me" -Headers $h
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/metrics/overview?recent_days=7" -Headers $h
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/overview" -Headers $h
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/users?offset=0&limit=50" -Headers $h
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/terms?offset=0&limit=50" -Headers $h
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/saves?offset=0&limit=50" -Headers $h
```

**Bash / curl**

```bash
TOKEN="$(curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test@pangyopass.com","password":"YOUR_PASSWORD"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")"

curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/admin/ping
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/admin/me
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/admin/metrics/overview?recent_days=7"
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/admin/overview
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/admin/users?offset=0&limit=50"
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/admin/terms?offset=0&limit=50"
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/admin/saves?offset=0&limit=50"
```

- 일반 사용자(`is_admin = 0`) 토큰으로 `/admin/*`를 호출하면 **403** (`Admin access required`)입니다.
- Swagger(`http://127.0.0.1:8000/docs`)에서 **Authorize**에 `Bearer <access_token>`을 넣고 동일 엔드포인트를 시험할 수 있습니다.

## DB 스키마 보강 (기존 `pangyopass.db` 사용 시)

새 컬럼이 모델에만 추가되고 `create_all`은 기존 테이블을 **수정하지 않습니다.**

- **SQLite 로컬 개발**: 서버 기동 시 `db/sqlite_migrate.py`가 `users.is_admin` 컬럼이 없으면 **자동으로 `ALTER TABLE`을 한 번 실행**합니다. 수동 실행이 필요 없는 경우가 많습니다.
- 그래도 직접 적용하려면 아래 SQL을 사용할 수 있습니다.

예: `users.is_admin` (관리자 여부, SQLite)

```sql
ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;
```

- `0` = 일반 사용자, `1` = 관리자 (`/admin/*`, `require_admin`)
- 새로 DB 파일을 비우고 다시 띄우면 `create_all`로 테이블이 새로 만들어지면서 컬럼이 포함됩니다.

## 현재 구현 상태 및 참고

- DB는 SQLite 기본 (`pangyopass.db`)
- `POST /auth/login`은 개발 편의를 위해 테스트 계정(`test@pangyopass.com`) 자동 시드 로직 포함
- 검색 API는 더미 데이터 기반

## 추후 확장 예정

- 북마크/용어 CRUD 고도화
- Refresh Token 구조
- Alembic 마이그레이션 도입
- 예외 처리 전역 핸들러 고도화
- (선택) 관리자 API 접근 감사 로그
