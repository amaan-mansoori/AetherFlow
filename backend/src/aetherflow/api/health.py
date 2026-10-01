"""Liveness and readiness endpoints."""

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from aetherflow.api.dependencies import get_request_db_session
from aetherflow.api.errors import ApiError
from aetherflow.observability.metrics import METRICS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])
database_session = Depends(get_request_db_session)


@router.get("/health/live", response_model=dict[str, str])
async def liveness() -> dict[str, str]:
    """Report process liveness without checking external dependencies."""

    return {"status": "alive"}


@router.get("/health/ready", response_model=dict[str, str])
async def readiness(
    session: AsyncSession = database_session,
) -> dict[str, str]:
    """Report readiness only when the required database dependency responds."""

    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("readiness_database_unavailable")
        raise ApiError(
            "DEPENDENCY_UNAVAILABLE",
            "The database is unavailable.",
            503,
        ) from exc
    return {"status": "ready", "database": "ready"}


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose application metrics in Prometheus text format."""

    return Response(METRICS.render(), media_type="text/plain; version=0.0.4")
