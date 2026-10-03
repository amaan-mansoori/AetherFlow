"""Job lifecycle and management endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from aetherflow.api.dependencies import get_request_db_session
from aetherflow.auth.policies import require_authenticated_user
from aetherflow.infrastructure.database.models import Job, JobState, User
from aetherflow.jobs.idempotency import validate_idempotency_key
from aetherflow.jobs.schemas import (
    JobAttemptResponse,
    JobCreateRequest,
    JobDetailResponse,
    JobEventResponse,
    JobResponse,
)
from aetherflow.jobs.service import (
    cancel_job,
    get_job,
    get_job_attempts,
    get_job_events,
    list_jobs,
    submit_job,
)
from aetherflow.observability.context import get_request_id

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
db_session = Depends(get_request_db_session)
authenticated_user = Depends(require_authenticated_user)


def _to_job_detail(job: Job) -> dict[str, Any]:
    latest_attempt = job.attempts[-1] if job.attempts else None
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
        "input": job.input,
        "configuration": job.configuration,
        "retry_policy": job.retry_policy,
        "metadata": job.metadata_,
        "result": job.result,
        "latest_attempt": latest_attempt,
    }


def _to_job_summary(job: Job) -> dict[str, Any]:
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


@router.post("", response_model=JobDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreateRequest,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: User = authenticated_user,
    session: AsyncSession = db_session,
) -> dict[str, Any]:
    validated_key = validate_idempotency_key(idempotency_key)
    job, is_new = await submit_job(
        session=session,
        user=user,
        payload=payload,
        idempotency_key=validated_key,
        request_id=get_request_id(),
    )
    if not is_new:
        response.status_code = status.HTTP_200_OK
    return _to_job_detail(job)


@router.get("", response_model=list[JobResponse])
async def list_user_jobs(
    state: Annotated[JobState | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = authenticated_user,
    session: AsyncSession = db_session,
) -> list[dict[str, Any]]:
    jobs = await list_jobs(session, user, state=state, limit=limit, offset=offset)
    return [_to_job_summary(job) for job in jobs]


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(
    job_id: UUID,
    user: User = authenticated_user,
    session: AsyncSession = db_session,
) -> dict[str, Any]:
    job = await get_job(session, user, job_id)
    return _to_job_detail(job)


@router.get("/{job_id}/events", response_model=list[JobEventResponse])
async def get_events(
    job_id: UUID,
    user: User = authenticated_user,
    session: AsyncSession = db_session,
) -> list[JobEventResponse]:
    events = await get_job_events(session, user, job_id)
    return [JobEventResponse.model_validate(e) for e in events]


@router.get("/{job_id}/attempts", response_model=list[JobAttemptResponse])
async def get_attempts(
    job_id: UUID,
    user: User = authenticated_user,
    session: AsyncSession = db_session,
) -> list[JobAttemptResponse]:
    attempts = await get_job_attempts(session, user, job_id)
    return [JobAttemptResponse.model_validate(a) for a in attempts]


@router.post("/{job_id}/cancel", response_model=JobDetailResponse)
async def cancel_job_endpoint(
    job_id: UUID,
    user: User = authenticated_user,
    session: AsyncSession = db_session,
) -> dict[str, Any]:
    job = await cancel_job(session, user, job_id, request_id=get_request_id())
    return _to_job_detail(job)
