"""ADMIN-only operational control-plane endpoints."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from aetherflow.api.dependencies import get_request_db_session
from aetherflow.auth.policies import require_admin
from aetherflow.infrastructure.database.models import Job, JobState, User
from aetherflow.jobs.admin import (
    get_admin_job_detail,
    list_admin_jobs,
    redact_operational_value,
)
from aetherflow.jobs.schemas import (
    AdminJobDetailResponse,
    AdminJobResponse,
)
from aetherflow.jobs.service import cancel_job
from aetherflow.observability.context import get_request_id
from aetherflow.observability.metrics import METRICS

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
db_session = Depends(get_request_db_session)
admin_user = Depends(require_admin)


def _date_range_is_utc(value: datetime | None, name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        from aetherflow.api.errors import ApiError

        raise ApiError("VALIDATION_ERROR", f"{name} must include a timezone.", 400)


def _summary(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "user_id": job.user_id,
        "type": job.type,
        "model": job.model,
        "state": job.state,
        "priority": job.priority,
        "timeout_seconds": job.timeout_seconds,
        "version": job.version,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "schedule_at": job.schedule_at,
    }


def _detail(
    job: Job,
    attempts: list[Any],
    events: list[Any],
    dispatches: list[Any],
) -> dict[str, object]:
    return {
        **_summary(job),
        "retry_policy": redact_operational_value(job.retry_policy),
        "metadata": redact_operational_value(job.metadata_),
        "execution_owner": job.execution_owner,
        "execution_dispatch_version": job.execution_dispatch_version,
        "execution_lease_until": job.execution_lease_until,
        "attempts": [
            {
                "id": attempt.id,
                "job_id": attempt.job_id,
                "attempt_number": attempt.attempt_number,
                "status": attempt.status,
                "worker_id": attempt.worker_id,
                "provider": attempt.provider,
                "model": attempt.model,
                "error_class": attempt.error_class,
                "error_message": redact_operational_value(attempt.error_message),
                "retry_decision": attempt.retry_decision,
                "usage": redact_operational_value(attempt.usage),
                "trace_id": attempt.trace_id,
                "started_at": attempt.started_at,
                "completed_at": attempt.completed_at,
            }
            for attempt in attempts
        ],
        "events": [
            {
                "id": event.id,
                "job_id": event.job_id,
                "event_type": event.event_type,
                "prior_state": event.prior_state,
                "next_state": event.next_state,
                "actor": event.actor,
                "payload": redact_operational_value(event.payload),
                "created_at": event.created_at,
            }
            for event in events
        ],
        "dispatches": [
            {
                "id": dispatch.id,
                "job_id": dispatch.job_id,
                "job_version": dispatch.job_version,
                "message_type": dispatch.message_type,
                "schema_version": dispatch.schema_version,
                "enqueued_at": dispatch.enqueued_at,
                "created_at": dispatch.created_at,
                "published_at": dispatch.published_at,
                "attempt_count": dispatch.attempt_count,
                "failure_category": dispatch.failure_category,
                "publication_state": dispatch.publication_state,
                "available_at": dispatch.available_at,
                "next_attempt_at": dispatch.next_attempt_at,
                "last_error": redact_operational_value(dispatch.last_error),
            }
            for dispatch in dispatches
        ],
    }


@router.get("/jobs", response_model=list[AdminJobResponse])
async def list_jobs(
    job_id: UUID | None = None,
    user_id: UUID | None = None,
    state: JobState | None = None,
    job_type: Annotated[str | None, Query(max_length=64)] = None,
    model: Annotated[str | None, Query(max_length=64)] = None,
    provider: Annotated[str | None, Query(max_length=64)] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    schedule_from: datetime | None = None,
    schedule_to: datetime | None = None,
    priority: Annotated[int | None, Query(ge=0, le=10)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    _admin: User = admin_user,
    session: AsyncSession = db_session,
) -> list[dict[str, object]]:
    for name, value in (
        ("created_from", created_from),
        ("created_to", created_to),
        ("schedule_from", schedule_from),
        ("schedule_to", schedule_to),
    ):
        _date_range_is_utc(value, name)
    jobs = await list_admin_jobs(
        session,
        job_id=job_id,
        user_id=user_id,
        state=state,
        job_type=job_type,
        model=model,
        provider=provider,
        created_from=created_from,
        created_to=created_to,
        schedule_from=schedule_from,
        schedule_to=schedule_to,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    METRICS.inc("aetherflow_admin_operations_total", operation="list_jobs", outcome="success")
    return [_summary(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=AdminJobDetailResponse)
async def get_job(
    job_id: UUID,
    child_limit: Annotated[int, Query(ge=1, le=100)] = 100,
    _admin: User = admin_user,
    session: AsyncSession = db_session,
) -> dict[str, object]:
    result = await get_admin_job_detail(session, job_id, child_limit=child_limit)
    METRICS.inc("aetherflow_admin_operations_total", operation="get_job", outcome="success")
    return _detail(*result)


@router.post("/jobs/{job_id}/cancel", response_model=AdminJobDetailResponse)
async def cancel_admin_job(
    job_id: UUID,
    _admin: User = admin_user,
    session: AsyncSession = db_session,
) -> dict[str, object]:
    job = await cancel_job(
        session,
        _admin,
        job_id,
        request_id=get_request_id(),
        audit_admin_action=True,
    )
    result = await get_admin_job_detail(session, job.id)
    METRICS.inc("aetherflow_admin_operations_total", operation="cancel_job", outcome="success")
    return _detail(*result)
