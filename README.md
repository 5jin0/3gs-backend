# 3gs-backend (PangyoPass Backend)

## Quick start

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Structure (initial)

- `app/`: FastAPI application entrypoint (`app/main.py`)
- `routers/`: API routers (domain-separated, aggregated in `routers/api.py`)
- `schemas/`: Pydantic request/response schemas (to be added per domain)
- `core/`: shared config/security utilities (to be expanded)
