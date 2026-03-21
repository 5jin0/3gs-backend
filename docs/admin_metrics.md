# 관리자 분석 API · 이벤트 계약

모든 `/admin/*` 경로는 **`Authorization: Bearer <JWT>`** 와 DB의 **`users.is_admin = 1`** 이 필요합니다.  
미인증 **401**, 비관리자 **403** (`Admin access required`).

응답은 공통으로 `schemas/common.ApiResponse` 형태입니다.

```json
{ "success": true, "data": { ... }, "message": "..." }
```

상세 필드·비율 정의는 **각 엔드포인트의 OpenAPI**(`GET /docs`) 및 아래 **Pydantic 스키마** 이름을 기준으로 합니다.

---

## Next.js 관리자 분석 API (접두 설정 가능)

기본 URL 접두: **`/admin/analytics`** (환경변수 `PP_ADMIN_ANALYTICS_PREFIX` 로 변경).

| Method | Path | 설명 |
|--------|------|------|
| GET | `{prefix}/search-funnel?period=day\|week\|month` | 퍼널 비율(`start_rate`, `click_rate`, …) |
| GET | `{prefix}/search-ux?period=...` | UX·지연·이탈 등 |
| GET | `{prefix}/access-cohorts?period=...&group_by=...` | 히트맵 행렬 |
| GET | `{prefix}/retention?granularity=day\|week\|month` | 리텐션 행렬(가입 코호트: 최근 90일) |
| GET | `{prefix}/user-saved-counts?page=&page_size=&sort=` | 유저별 저장 횟수 |

스키마: `schemas/admin_analytics_frontend.py`. 구현: `routers/admin_analytics.py`, `services/admin_analytics_frontend.py`.

---

## 엔드포인트 요약 (기존 `/admin/metrics/*` 등)

| Method | Path | 스키마( data 타입 ) | 주요 소스 테이블 |
|--------|------|---------------------|------------------|
| GET | `/admin/ping` | `dict` | — |
| GET | `/admin/me` | `UserPublic` | `users` |
| GET | `/admin/overview` | `AdminOverview` | `users`, `terms`, `saved_terms` |
| GET | `/admin/metrics/overview` | `AdminMetricsOverview` | 여러 이벤트·카운터 테이블 |
| GET | `/admin/metrics/search-funnel` | `SearchFunnelMetrics` | `search_events` |
| GET | `/admin/metrics/search-timing` | `SearchTimingMetrics` | `search_events` |
| GET | `/admin/metrics/cohort-reaccess` | `CohortReaccessMetrics` | `user_access_events`, `users`, (옵션) `search_analytics_events` |
| GET | `/admin/metrics/retention` | `RetentionMetrics` | `users`, `user_access_events` |
| GET | `/admin/metrics/user-save-counts` | `AdminUserSaveCountResult` | `saved_terms` |
| GET | `/admin/users` | `AdminUserListResult` | `users` |
| GET | `/admin/terms` | `AdminTermListResult` | `terms` |
| GET | `/admin/saves` | `AdminSaveListResult` | `saved_terms`, `terms` |

구현 위치: `routers/admin.py`, 집계는 `services/*.py`, 스키마는 `schemas/admin.py`.

---

## 이벤트 계약 (프론트·로깅과 공유)

### `search_events`

| `event_type` | 의미(요약) | 기록 위치(참고) |
|--------------|------------|-----------------|
| `search_start` | 검색 입력 시작 | `POST /terms/events/search-start` |
| `search_click` | 검색창/결과 클릭 등 | `POST /terms/events/search-click` |
| `suggestion_select` | 자동완성 제안 선택 | `POST /terms/events/suggestion-select` |
| `search_complete` | 검색 완료 | `POST /terms/events/search-complete` (라이프사이클) |
| `search_exit` | 검색 목록 이탈 | `POST /terms/events/search-exit` |

공통 컬럼: `user_id`, `keyword`, `created_at`.  
관리자 **퍼널·시간차** API는 위 타입 문자열을 그대로 집계합니다.

### `search_analytics_events`

| 필드 | 값 예시 | 비고 |
|------|---------|------|
| `event_type` | `search_complete`, `search_exit` | 라이프사이클 이벤트 |
| `cohort` | `new_user`, `existing_user` | 가입 7일 이내 여부 등 (`routers/terms._compute_user_cohort`) |

**코호트 재접속** API의 `cohort_mode=search_analytics` 는 이 테이블의 `cohort` 로 묶습니다.

### `user_access_events`

| `event_type` | 의미 |
|--------------|------|
| `login_success` | 로그인 성공 |
| `wordbook_view` | 단어장/워드북 화면 접근 등 |

**리텐션**·**코호트 재접속(일부)** 에서 활성·재로그인 판단에 `login_success` 를 사용합니다.

### `saved_terms`

- 유저별 단어장 저장 행. **유저별 저장 횟수** API는 `user_id` 그룹 `COUNT` 및 `created_at` 필터를 사용합니다.

---

## 쿼리 파라미터 관례

- **`start` / `end`**: 대부분 **UTC** 기준이며, timezone 없이 넘기면 UTC 로 간주하는 엔드포인트가 있습니다. OpenAPI 설명 참고.
- **기간 생략**: 퍼널·시간차·코호트·리텐션 등은 종종 **최근 7일(UTC)** 기본값.
- **페이지네이션**: `offset`, `limit` — 목록·`user-save-counts` 등.

---

## Swagger

로컬: `http://127.0.0.1:8000/docs` → **Authorize** 에 `Bearer <token>` 등록 후 호출.

---

## 변경 시 체크리스트

1. 새 `event_type` 을 쓰면 이 문서와 `SearchFunnelMetrics` 의 `KNOWN_TYPES` / 집계 로직을 함께 갱신할지 검토.
2. 관리자 전용 집계는 **`require_admin`** 유지.
3. SQLite 인덱스: 기간 조회가 많은 테이블은 `created_at` 인덱스 검토 (`db/sqlite_migrate.py` 등).
