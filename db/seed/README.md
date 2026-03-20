# 용어(판교어) 시드 데이터

엑셀을 DB에 넣을 때 컬럼만 맞추면 `Term` 모델과 1:1로 넣을 수 있습니다.

## 엑셀 / CSV 컬럼 → `terms` 테이블

| 엑셀 헤더   | DB 컬럼 (`Term`)   | 비고                                      |
|------------|-------------------|-------------------------------------------|
| 용어        | `term`            | 인덱스 있음. 동일 표기 중복 행 허용(MVP).   |
| 원래 의미   | `original_meaning` | `Text`                                   |
| 뜻         | `definition`      | `Text`                                   |
| 사용 예시   | `example`         | 비어 있으면 `""` 로 넣기                   |

`id`, `created_at`, `updated_at`는 DB/ORM 기본값으로 채워도 됩니다.

## 예시 (pandas + openpyxl, 개념 스케치)

```python
# pip install pandas openpyxl sqlalchemy
import pandas as pd
from sqlalchemy.orm import Session

# df = pd.read_excel("terms.xlsx")
# for _, row in df.iterrows():
#     session.add(Term(
#         term=str(row["용어"]).strip(),
#         original_meaning=str(row["원래 의미"]).strip(),
#         definition=str(row["뜻"]).strip(),
#         example="" if pd.isna(row.get("사용 예시")) else str(row["사용 예시"]).strip(),
#     ))
# session.commit()
```

실제 스크립트는 `app` 경로/`get_db` 연결 방식에 맞춰 프로젝트 루트에서 실행하면 됩니다.

## 기존 SQLite DB를 이미 쓰고 있다면

`terms` 테이블에 예전 컬럼(`name`, `meaning` 등)이 있으면 스키마가 맞지 않습니다. 개발 중이라면 `pangyopass.db` 삭제 후 서버를 다시 띄우면 `create_all`로 새 스키마가 생성됩니다.
