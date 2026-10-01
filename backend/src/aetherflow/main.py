"""FastAPI application factory and process entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from aetherflow.api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from aetherflow.api.router import router
from aetherflow.config.logging import configure_logging
from aetherflow.config.settings import Settings, get_settings
from aetherflow.infrastructure.database.session import create_engine, create_session_factory
from aetherflow.infrastructure.redis import create_redis_client
from aetherflow.observability.middleware import MetricsMiddleware
from aetherflow.observability.rate_limit import RateLimitMiddleware
from aetherflow.observability.request_id import RequestIdMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application with isolated settings and database resources."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.logging_level)
    engine = create_engine(resolved_settings)
    session_factory = create_session_factory(engine)
    redis_client = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal redis_client
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        if resolved_settings.redis_enabled:
            redis_client = create_redis_client(resolved_settings)
        app.state.redis_client = redis_client
        app.state.rate_limit_store = redis_client.rate_limits if redis_client else None
        if redis_client is not None:
            try:
                await redis_client.ping()
                logger.info("redis_ready")
            except Exception:
                logger.warning("redis_unavailable_rate_limiting_fail_open")
        logger.info("application_started")
        try:
            yield
        finally:
            if redis_client is not None:
                await redis_client.close()
            await engine.dispose()
            logger.info("application_stopped")

    app = FastAPI(
        title=resolved_settings.application_name,
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        settings=resolved_settings,
    )
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "POST", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Request-ID",
            "Idempotency-Key",
        ],
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(router)
    return app


app = create_app()
