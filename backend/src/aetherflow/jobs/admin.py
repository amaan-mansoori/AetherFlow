"""Bounded, redacted administrative job inspection queries."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from aetherflow.api.errors import ApiError
from aetherflow.infrastructure.database.models import (
    Job,
    JobAttempt,
    JobEvent,
    JobState,
    OutboxDispatch,
)

MAX_ADMIN_PAGE_SIZE = 100
MAX_REDACTED_ITEMS = 50
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "credential",
    "authorization",
    "api_key",
    "private_key",
)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def redact_operational_value(value: object, *, depth: int = 0) -> object:
    """Bound user-controlled operational values without exposing likely secrets."""
    if depth >= 3:
        return "[truncated]"
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_REDACTED_ITEMS:
                result["[truncated]"] = True
                break
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                result[str(key)] = "[redacted]"
            else:
                result[str(key)] = redact_operational_value(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [
            redact_operational_value(item, depth=depth + 1) for item in value[:MAX_REDACTED_ITEMS]
        ]
    if isinstance(value, str):
        return value[:400] + ("...[truncated]" if len(value) > 400 else "")
    return value


async def list_admin_jobs(
    session: AsyncSession,
    *,
    job_id: UUID | None = None,
    user_id: UUID | None = None,
    state: JobState | None = None,
    job_type: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    schedule_from: datetime | None = None,
    schedule_to: datetime | None = None,
    priority: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Job]:
    if limit < 1 or limit > MAX_ADMIN_PAGE_SIZE:
        raise ApiError("VALIDATION_ERROR", "limit must be between 1 and 100.", 400)
    if offset < 0:
        raise ApiError("VALIDATION_ERROR", "offset must not be negative.", 400)
    if created_from is not None and created_to is not None and created_from > created_to:
        raise ApiError("VALIDATION_ERROR", "created_from must not exceed created_to.", 400)
    if schedule_from is not None and schedule_to is not None and schedule_from > schedule_to:
        raise ApiError("VALIDATION_ERROR", "schedule_from must not exceed schedule_to.", 400)

    query = select(Job)
    filters = []
    if job_id is not None:
        filters.append(Job.id == job_id)
    if user_id is not None:
        filters.append(Job.user_id == user_id)
    if state is not None:
        filters.append(Job.state == state)
    if job_type is not None:
        filters.append(Job.type == job_type.strip())
    if model is not None:
        filters.append(Job.model == model.strip())
    if provider is not None:
        filters.append(
            exists(
                select(JobAttempt.id).where(
                    JobAttempt.job_id == Job.id,
                    JobAttempt.provider == provider.strip(),
                )
            )
        )
    if created_from is not None:
        filters.append(Job.created_at >= _utc(created_from))
    if created_to is not None:
        filters.append(Job.created_at <= _utc(created_to))
    if schedule_from is not None:
        filters.append(Job.schedule_at >= _utc(schedule_from))
    if schedule_to is not None:
        filters.append(Job.schedule_at <= _utc(schedule_to))
    if priority is not None:
        filters.append(Job.priority == priority)
    query = (
        query.where(*filters)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.scalars(query)).all())


async def get_admin_job_detail(
    session: AsyncSession,
    job_id: UUID,
    *,
    child_limit: int = 100,
) -> tuple[Job, list[JobAttempt], list[JobEvent], list[OutboxDispatch]]:
    if child_limit < 1 or child_limit > MAX_ADMIN_PAGE_SIZE:
        raise ApiError("VALIDATION_ERROR", "child_limit must be between 1 and 100.", 400)
    job = await session.scalar(select(Job).where(Job.id == job_id))
    if job is None:
        raise ApiError("NOT_FOUND", "Job not found.", 404)
    attempts = list(
        (
            await session.scalars(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_id)
                .order_by(JobAttempt.attempt_number.asc())
                .limit(child_limit)
            )
        ).all()
    )
    events = list(
        (
            await session.scalars(
                select(JobEvent)
                .where(JobEvent.job_id == job_id)
                .order_by(JobEvent.created_at.asc(), JobEvent.id.asc())
                .limit(child_limit)
            )
        ).all()
    )
    dispatches = list(
        (
            await session.scalars(
                select(OutboxDispatch)
                .where(OutboxDispatch.job_id == job_id)
                .order_by(OutboxDispatch.created_at.asc(), OutboxDispatch.id.asc())
                .limit(child_limit)
            )
        ).all()
    )
    return job, attempts, events, dispatches
