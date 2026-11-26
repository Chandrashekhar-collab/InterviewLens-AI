"""FastAPI application entry point and lifespan configuration."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api_router import api_router
from app.config import settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown procedures."""
    setup_logging()
    Path(settings.RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)
    from app.engines.speech.compat import apply_pyav_compatibility_patch
    apply_pyav_compatibility_patch()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


def create_application(use_lifespan: bool = True) -> FastAPI:
    """Create and configure the FastAPI application instance.

    Args:
        use_lifespan: When False, skips the lifespan context manager. Set to
            False in tests to avoid event-loop conflicts with aiosqlite and
            pytest-asyncio fixtures.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="InterviewLens AI - Adaptive AI-Based Interview & Presentation Assessment Platform API",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan if use_lifespan else None,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)

    # Include API Routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Direct health check at root /health as well
    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def root_health():
        return {
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return app


app = create_application()
