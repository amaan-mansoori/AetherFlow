"""Job domain application services."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aetherflow.api.errors import ApiError
from aetherflow.infrastructure.database.models import (
    IdempotencyRecord,
    Job,
    JobAttempt,
    JobEvent,
    JobResult,
    JobState,
    User,
    utc_now,
)
from aetherflow.jobs.idempotency import compute_payload_fingerprint
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.state_machine import is_terminal_state, validate_transition


async def is_admin_user(session: AsyncSession, user: User) -> bool:
    """Return True if the user has the ADMIN role."""
    if "roles" not in user.__dict__:
        await session.refresh(user, attribute_names=["roles"])
    return any(role.name == "ADMIN" for role in user.roles)


async def submit_job(
    session: AsyncSession,
    user: User,
    payload: JobCreateRequest,
    idempotency_key: str,
    request_id: str | None = None,
) -> tuple[Job, bool]:
    """Submit a new job with strict idempotency and atomic creation.

    Returns:
        tuple[Job, bool]: (job, is_newly_created)
    """
    fingerprint = compute_payload_fingerprint(payload.model_dump())

    # Fast path: check for existing idempotency record
    existing_record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.principal_id == user.id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    if existing_record is not None:
        if existing_record.fingerprint != fingerprint:
            raise ApiError(
                "IDEMPOTENCY_KEY_REUSED",
                "The idempotency key was used with a different request.",
                409,
            )
        existing_job = await session.scalar(
            select(Job)
            .options(selectinload(Job.result), selectinload(Job.attempts))
            .where(Job.id == existing_record.job_id)
        )
        if existing_job is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        return existing_job, False

    # Insert path: create Job and IdempotencyRecord atomically
    job = Job(
        user_id=user.id,
        type=payload.type,
        model=payload.model,
        input=payload.input,
        configuration=payload.configuration,
        priority=payload.priority,
        timeout_seconds=payload.timeout_seconds,
        retry_policy=payload.retry_policy.model_dump(),
        metadata_=payload.metadata,
        state=JobState.ACCEPTED,
        version=1,
    )
    session.add(job)
    await session.flush()

    event = JobEvent(
        job_id=job.id,
        event_type="JOB_ACCEPTED",
        prior_state=None,
        next_state=JobState.ACCEPTED,
        actor=f"user:{user.id}",
        payload={"idempotency_key": idempotency_key, "request_id": request_id},
    )
    session.add(event)

    record = IdempotencyRecord(
        principal_id=user.id,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
        job_id=job.id,
        response_status=201,
    )
    session.add(record)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # Race condition resolution: reload committed record
        conflict_record = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.principal_id == user.id,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if conflict_record is None:
            raise ApiError("CONFLICT", "A concurrent submission conflict occurred.", 409) from exc
        if conflict_record.fingerprint != fingerprint:
            raise ApiError(
                "IDEMPOTENCY_KEY_REUSED",
                "The idempotency key was used with a different request.",
                409,
            ) from exc
        resolved_job = await session.scalar(
            select(Job)
            .options(selectinload(Job.result), selectinload(Job.attempts))
            .where(Job.id == conflict_record.job_id)
        )
        if resolved_job is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404) from exc
        return resolved_job, False

    await session.refresh(job)
    return job, True


async def get_job(session: AsyncSession, user: User, job_id: UUID) -> Job:
    """Retrieve a job enforcing ownership or ADMIN authorization."""
    query = select(Job).options(selectinload(Job.result), selectinload(Job.attempts))
    if await is_admin_user(session, user):
        query = query.where(Job.id == job_id)
    else:
        query = query.where(Job.id == job_id, Job.user_id == user.id)

    job = await session.scalar(query)
    if job is None:
        raise ApiError("NOT_FOUND", "Job not found.", 404)
    return job


async def list_jobs(
    session: AsyncSession,
    user: User,
    *,
    state: JobState | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Job]:
    """List jobs with bounded pagination and deterministic ordering."""
    query = select(Job).options(selectinload(Job.result), selectinload(Job.attempts))
    if not await is_admin_user(session, user):
        query = query.where(Job.user_id == user.id)
    if state is not None:
        query = query.where(Job.state == state)

    query = query.order_by(Job.created_at.desc(), Job.id.desc()).offset(offset).limit(limit)
    jobs = await session.scalars(query)
    return list(jobs.all())


async def cancel_job(
    session: AsyncSession,
    user: User,
    job_id: UUID,
    request_id: str | None = None,
) -> Job:
    """Request job cancellation via the authoritative state machine."""
    query = (
        select(Job)
        .options(selectinload(Job.result), selectinload(Job.attempts))
        .where(Job.id == job_id)
    )
    if not await is_admin_user(session, user):
        query = query.where(Job.user_id == user.id)

    job = await session.scalar(query)
    if job is None:
        raise ApiError("NOT_FOUND", "Job not found.", 404)

    # Idempotent repeated cancellation
    if job.state == JobState.CANCEL_REQUESTED:
        return job

    # Terminal state cancellation forbidden
    if is_terminal_state(job.state):
        raise ApiError(
            "INVALID_STATE_TRANSITION",
            f"Cannot cancel job in terminal state '{job.state}'.",
            409,
        )

    # Validate transition through state machine
    validate_transition(job.state, JobState.CANCEL_REQUESTED)

    return await transition_job_state(
        session,
        job_id,
        JobState.CANCEL_REQUESTED,
        actor=f"user:{user.id}",
        payload={"request_id": request_id, "reason": "user_cancellation_request"},
        expected_version=job.version,
    )


async def transition_job_state(
    session: AsyncSession,
    job_id: UUID,
    target_state: JobState,
    actor: str,
    payload: dict[str, Any] | None = None,
    expected_version: int | None = None,
) -> Job:
    """Apply a state transition with explicit state/version compare-and-set semantics."""
    job = await session.scalar(
        select(Job)
        .options(selectinload(Job.result), selectinload(Job.attempts))
        .where(Job.id == job_id)
        .with_for_update()
    )
    if job is None:
        raise ApiError("NOT_FOUND", "Job not found.", 404)

    validate_transition(job.state, target_state)

    prior_state = job.state
    prior_version = job.version if expected_version is None else expected_version
    updated_at = utc_now()
    cas_result = cast(
        CursorResult[Any],
        await session.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.state == prior_state,
                Job.version == prior_version,
            )
            .values(state=target_state, version=Job.version + 1, updated_at=updated_at)
        ),
    )
    if cas_result.rowcount != 1:
        await session.rollback()
        await session.refresh(job)
        raise ApiError(
            "CONFLICT",
            "The job changed before the requested state transition was applied.",
            409,
        )

    event = JobEvent(
        job_id=job.id,
        event_type=(
            "CANCEL_REQUESTED"
            if target_state == JobState.CANCEL_REQUESTED
            else f"STATE_CHANGED_TO_{target_state}"
        ),
        prior_state=prior_state,
        next_state=target_state,
        actor=actor,
        payload=payload or {},
    )
    session.add(event)
    await session.commit()
    await session.refresh(job)
    return job


async def record_job_attempt(
    session: AsyncSession,
    job_id: UUID,
    attempt_number: int,
    status: str,
    *,
    worker_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    error_class: str | None = None,
    error_message: str | None = None,
    retry_decision: str | None = None,
    usage: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> JobAttempt:
    """Record a job execution attempt with unique attempt numbering."""
    job = await session.scalar(select(Job).where(Job.id == job_id))
    if job is None:
        raise ApiError("NOT_FOUND", "Job not found.", 404)
    if job.state != JobState.RUNNING:
        raise ApiError(
            "INVALID_STATE_TRANSITION",
            f"Cannot record an attempt while job is in state '{job.state}'.",
            409,
        )

    attempt = JobAttempt(
        job_id=job_id,
        attempt_number=attempt_number,
        status=status,
        worker_id=worker_id,
        provider=provider,
        model=model,
        error_class=error_class,
        error_message=error_message,
        retry_decision=retry_decision,
        usage=usage,
        trace_id=trace_id,
    )
    session.add(attempt)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            "CONFLICT",
            f"Attempt number {attempt_number} already exists for job {job_id}.",
            409,
        ) from exc
    await session.refresh(attempt)
    return attempt


async def record_job_result(
    session: AsyncSession,
    job_id: UUID,
    output: dict[str, Any],
    *,
    schema_version: str = "v1",
    usage: dict[str, Any] | None = None,
) -> JobResult:
    """Record validated output for a job with uniqueness protection."""
    job = await session.scalar(select(Job).where(Job.id == job_id))
    if job is None:
        raise ApiError("NOT_FOUND", "Job not found.", 404)
    if job.state not in {JobState.RUNNING, JobState.CANCEL_REQUESTED}:
        raise ApiError(
            "INVALID_STATE_TRANSITION",
            f"Cannot record a result while job is in state '{job.state}'.",
            409,
        )

    result = JobResult(
        job_id=job_id,
        schema_version=schema_version,
        output=output,
        usage=usage,
    )
    session.add(result)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            "CONFLICT",
            f"A result already exists for job {job_id}.",
            409,
        ) from exc
    await session.refresh(result)
    return result


async def get_job_events(session: AsyncSession, user: User, job_id: UUID) -> list[JobEvent]:
    """Retrieve audit lifecycle events for a visible job."""
    # Ensure job is visible to user
    await get_job(session, user, job_id)
    events = await session.scalars(
        select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc())
    )
    return list(events.all())


async def get_job_attempts(session: AsyncSession, user: User, job_id: UUID) -> list[JobAttempt]:
    """Retrieve execution attempts for a visible job."""
    # Ensure job is visible to user
    await get_job(session, user, job_id)
    attempts = await session.scalars(
        select(JobAttempt)
        .where(JobAttempt.job_id == job_id)
        .order_by(JobAttempt.attempt_number.asc())
    )
    return list(attempts.all())
