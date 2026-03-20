# 판교어 사전 시드 적재

엑셀/CSV의 한 행을 `terms` 테이블 한 행으로 넣습니다.

## 파일 형식

- **Excel**: `.xlsx`, `.xlsm` (헤더 첫 행)
- **CSV**: `.csv` (UTF-8 BOM 권장 → `utf-8-sig`)

## 필수 컬럼 (헤더 이름 정확히 일치)

| 헤더      | DB 필드            |
|----------|-------------------|
| 용어      | `term`            |
| 원래 의미 | `original_meaning` |
| 뜻       | `definition`      |
| 사용 예시 | `example`         |

- **중복 용어**: 같은 `term` 문자열(strip 후)이 DB에 이미 있으면 삽입하지 않습니다.
- **파일 내 중복**: 같은 파일에서 동일 `term`이 두 번 나오면 첫 행만 반영합니다.
- **빈 용어** 또는 **원래 의미/뜻 누락** 행은 스킵하고 경고를 남깁니다.

## 준비

프로젝트 루트(`3gs-backend`)에서:

```powershell
py -m pip install -r requirements-seed.txt
```

## 실행

프로젝트 루트에서 (SQLite 기본 경로는 `app/core/config.py`의 `database_url`과 동일):

```powershell
# 기본: data/pangyo_terms.csv
py scripts/seed_terms.py

py scripts/seed_terms.py .\data\pangyo_terms.xlsx
```

실제 커밋 없이 건수만 확인:

```powershell
py scripts/seed_terms.py .\data\pangyo_terms.xlsx --dry-run
```

다른 DB 파일을 쓰려면 환경 변수로 지정:

```powershell
$env:PP_DATABASE_URL = "sqlite:///./other.db"
py scripts/seed_terms.py .\data\pangyo_terms.xlsx
```

테이블은 기본적으로 스크립트가 `create_all`로 없을 때 생성합니다. 이미 마이그레이션으로 관리 중이면:

```powershell
py scripts/seed_terms.py .\data\terms.csv --no-ensure-schema
```

## 코드에서 재사용

같은 로직을 다른 스크립트에서 쓰려면 `db.seed.loader`를 import 합니다.

```python
from pathlib import Path
from db.seed.loader import read_terms_file, seed_terms_from_dataframe
from db.session import SessionLocal

df = read_terms_file(Path("terms.xlsx"))
db = SessionLocal()
try:
    stats = seed_terms_from_dataframe(db, df, dry_run=False)
finally:
    db.close()
```

## 스키마 불일치 시

`terms` 테이블 정의를 바꾼 뒤라면 개발용 SQLite는 파일을 지우고 FastAPI를 한 번 띄운 뒤 시드를 다시 넣는 것이 가장 간단합니다.
