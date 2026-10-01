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
from aetherflow.infrastructure.kafka import KafkaDispatcher
from aetherflow.jobs.dispatch import JobDispatcher
from aetherflow.observability.request_id import RequestIdMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application with isolated settings and database resources."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.logging_level)
    engine = create_engine(resolved_settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        dispatcher: JobDispatcher | None = None
        if resolved_settings.kafka_enabled:
            dispatcher = await KafkaDispatcher.create(resolved_settings)
        app.state.dispatcher = dispatcher
        logger.info("application_started")
        try:
            yield
        finally:
            if dispatcher is not None:
                await dispatcher.close()
            await engine.dispose()
            logger.info("application_stopped")

    app = FastAPI(
        title=resolved_settings.application_name,
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
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
