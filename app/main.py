"""Application entrypoint.

Run locally:
    uvicorn app.main:app --reload

This module keeps wiring (routers/middleware) in one place so that
feature modules can stay isolated and easy to expand later.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from db.base import Base
from db import models  # noqa: F401 - ensure ORM models are imported
from db.session import engine
from routers.api import router as root_router
from routers.auth import router as auth_router
from routers.health import router as health_router
from routers.terms import router as terms_router


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""

    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    @app.on_event("startup")
    def on_startup() -> None:
        # Creates tables for all imported ORM models.
        Base.metadata.create_all(bind=engine)

    # CORS for Next.js frontend (local/dev/prod configurable via env)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers. New feature routers can be added under routers/
    # and registered here with include_router().
    #
    # For future expansion, add new routers like:
    #   from routers.terms import router as terms_router
    #   app.include_router(terms_router)
    app.include_router(root_router)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(terms_router)

    return app


app = create_app()

