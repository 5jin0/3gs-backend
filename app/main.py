"""Application entrypoint.

Run locally:
    uvicorn app.main:app --reload

This module keeps wiring (routers/middleware) in one place so that
feature modules can stay isolated and easy to expand later.
"""

from fastapi import FastAPI

from routers.api import api_router


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""

    app = FastAPI(
        title="PangyoPass API",
        version="0.1.0",
    )

    # Register API routers. New feature routers can be added under routers/
    # and included from routers/api.py without changing this file much.
    app.include_router(api_router)

    return app


app = create_app()

