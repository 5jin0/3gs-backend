"""Top-level API router aggregator.

Keep this as the single place to include domain routers (auth/terms/health/etc).
This makes it easy to add new routes without touching app/main.py.
"""

from fastapi import APIRouter

from routers.health import router as health_router

api_router = APIRouter()

# Example placeholder route for sanity-checking the server is running.
# We'll add dedicated routers (e.g., health/auth/terms) in later steps.
@api_router.get("/", tags=["root"])
def root() -> dict:
    return {"message": "PangyoPass backend is running"}


# Domain routers
api_router.include_router(health_router)

