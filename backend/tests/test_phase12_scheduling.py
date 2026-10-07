"""Phase 12 durable one-shot scheduling coverage."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from aetherflow.infrastructure.database.models import (
    Job,
    JobEvent,
    JobState,
    OutboxDispatch,
)
from aetherflow.jobs.dispatch import LocalDispatcher
from aetherflow.jobs.outbox import OutboxPublisher
from aetherflow.jobs.scheduler import DurableScheduler
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.service import cancel_job, submit_job
from aetherflow.jobs.worker import Worker, WorkerResultStatus
from aetherflow.runtime.scheduler import SchedulerLifecycle, SchedulerRuntime


async def create_token(client, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery staple"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct horse battery staple"},
    )
    return str(response.json()["access_token"])


async def create_scheduled_job(app, email: str, schedule_at: datetime):
    from aetherflow.auth.service import register_user

    async with app.state.session_factory() as session:
        user = await register_user(session, email, "correct horse battery staple", None)
        job, is_new = await submit_job(
            session,
            user,
            JobCreateRequest(
                model="scheduled-model",
                input={"prompt": "later"},
                schedule_at=schedule_at,
            ),
            f"schedule-{email}",
        )
        return job, user, is_new


def test_schedule_at_requires_timezone_and_normalizes_to_utc() -> None:
    with pytest.raises(ValidationError):
        JobCreateRequest(model="model", input={}, schedule_at=datetime(2026, 10, 2, 12, 0))

    payload = JobCreateRequest(
        model="model",
        input={},
        schedule_at=datetime(2026, 10, 2, 17, 30, tzinfo=UTC).astimezone(UTC),
    )
    assert payload.schedule_at == datetime(2026, 10, 2, 17, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_api_exposes_future_schedule_and_replays_idempotently(client) -> None:
    token = await create_token(client, "scheduled-api@example.com")
    schedule_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    headers = {
        "Authorization": "Bearer " + token,
        "Idempotency-Key": "scheduled-api-key",
    }
    payload = {"model": "scheduled-model", "input": {}, "schedule_at": schedule_at}

    created = await client.post("/api/v1/jobs", json=payload, headers=headers)
    replay = await client.post("/api/v1/jobs", json=payload, headers=headers)

    assert created.status_code == 201
    assert replay.status_code == 200
    assert created.json()["state"] == "ACCEPTED"
    assert created.json()["schedule_at"].endswith(("Z", "+00:00"))
    assert replay.json()["id"] == created.json()["id"]


@pytest.mark.asyncio
async def test_future_submission_is_durable_without_an_outbox_intent(app) -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    job, _, is_new = await create_scheduled_job(app, "future-schedule@example.com", future)

    assert is_new is True
    async with app.state.session_factory() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None
        assert stored.state == JobState.ACCEPTED
        assert stored.schedule_at is not None
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OutboxDispatch)
                .where(OutboxDispatch.job_id == job.id)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_past_schedule_is_immediately_outbox_eligible(app) -> None:
    job, _, _ = await create_scheduled_job(
        app,
        "past-schedule@example.com",
        datetime.now(UTC) - timedelta(seconds=1),
    )

    async with app.state.session_factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OutboxDispatch)
                .where(OutboxDispatch.job_id == job.id)
            )
            == 1
        )
        stored = await session.get(Job, job.id)
        assert stored is not None and stored.state == JobState.ACCEPTED


@pytest.mark.asyncio
async def test_scheduler_activates_due_job_atomically(app) -> None:
    base = datetime.now(UTC)
    now = base + timedelta(seconds=5)
    job, _, _ = await create_scheduled_job(
        app, "due-schedule@example.com", base + timedelta(seconds=1)
    )
    async with app.state.session_factory() as session:
        await session.execute(
            Job.__table__.update()
            .where(Job.id == job.id)
            .values(schedule_at=base + timedelta(seconds=1))
        )
        await session.commit()

    scheduler = DurableScheduler(
        app.state.session_factory,
        scheduler_id="test-scheduler",
        now=lambda: now,
    )
    activations = await scheduler.poll_once(limit=10)

    assert len(activations) == 1
    assert activations[0].job_id == job.id
    async with app.state.session_factory() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None
        assert stored.state == JobState.QUEUED
        assert stored.version == 2
        intents = list(
            (
                await session.scalars(select(OutboxDispatch).where(OutboxDispatch.job_id == job.id))
            ).all()
        )
        assert len(intents) == 1
        assert intents[0].job_version == 2
        event = await session.scalar(
            select(JobEvent).where(
                JobEvent.job_id == job.id, JobEvent.event_type == "SCHEDULED_JOB_ACTIVATED"
            )
        )
        assert event is not None


@pytest.mark.asyncio
async def test_due_schedule_uses_existing_outbox_and_worker_path(app) -> None:
    base = datetime.now(UTC)
    now = base + timedelta(seconds=5)
    job, _, _ = await create_scheduled_job(
        app, "scheduled-worker@example.com", base + timedelta(seconds=1)
    )
    scheduler = DurableScheduler(
        app.state.session_factory,
        scheduler_id="test-scheduler",
        now=lambda: now,
    )
    await scheduler.poll_once()

    dispatcher = LocalDispatcher()
    publisher = OutboxPublisher(app.state.session_factory, dispatcher)
    assert await publisher.publish_once() is not None

    from aetherflow.jobs.providers import create_default_provider_executor

    executor = create_default_provider_executor(app.state.settings)
    try:
        result = await Worker(
            app.state.session_factory,
            dispatcher,
            executor,
            worker_id="scheduled-worker",
        ).run_once()
    finally:
        await executor.close()

    assert result.status == WorkerResultStatus.SUCCEEDED
    async with app.state.session_factory() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None and stored.state == JobState.SUCCEEDED


@pytest.mark.asyncio
async def test_scheduler_runtime_stops_and_disposes_resources() -> None:
    class FakeScheduler:
        async def poll_once(self, limit: int) -> list[object]:
            return []

    class FakeEngine:
        disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    engine = FakeEngine()
    runtime = SchedulerRuntime(
        FakeScheduler(),  # type: ignore[arg-type]
        engine,  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
        batch_size=1,
    )
    await runtime.start()
    await runtime.stop()

    assert runtime.lifecycle == SchedulerLifecycle.STOPPED
    assert engine.disposed is True


@pytest.mark.asyncio
async def test_scheduler_ignores_not_due_and_is_duplicate_safe(app) -> None:
    base = datetime.now(UTC)
    now = base
    job, _, _ = await create_scheduled_job(
        app, "not-due-schedule@example.com", base + timedelta(seconds=1)
    )
    scheduler = DurableScheduler(
        app.state.session_factory,
        scheduler_id="test-scheduler",
        now=lambda: now,
    )

    assert await scheduler.poll_once() == []
    async with app.state.session_factory() as session:
        await session.execute(
            Job.__table__.update().where(Job.id == job.id).values(schedule_at=now)
        )
        await session.commit()

    assert len(await scheduler.poll_once()) == 1
    assert await scheduler.poll_once() == []
    async with app.state.session_factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OutboxDispatch)
                .where(OutboxDispatch.job_id == job.id)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_cancellation_before_due_is_terminal_and_not_resurrected(app) -> None:
    now = datetime.now(UTC)
    job, user, _ = await create_scheduled_job(
        app, "cancel-schedule@example.com", now + timedelta(hours=1)
    )
    async with app.state.session_factory() as session:
        cancelled = await cancel_job(session, user, job.id)
        assert cancelled.state == JobState.CANCELLED
        repeated = await cancel_job(session, user, job.id)
        assert repeated.state == JobState.CANCELLED

    scheduler = DurableScheduler(
        app.state.session_factory,
        scheduler_id="test-scheduler",
        now=lambda: now + timedelta(hours=2),
    )
    assert await scheduler.poll_once() == []
    async with app.state.session_factory() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None and stored.state == JobState.CANCELLED
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OutboxDispatch)
                .where(OutboxDispatch.job_id == job.id)
            )
            == 0
        )
        event_types = list(
            await session.scalars(select(JobEvent.event_type).where(JobEvent.job_id == job.id))
        )
        assert event_types == ["JOB_ACCEPTED", "STATE_CHANGED_TO_CANCELLED"]


@pytest.mark.asyncio
async def test_cancelled_due_schedule_dispatch_is_acknowledged_without_execution(app) -> None:
    job, user, _ = await create_scheduled_job(
        app,
        "cancelled-due-schedule@example.com",
        datetime.now(UTC) - timedelta(seconds=1),
    )
    dispatcher = LocalDispatcher()
    publisher = OutboxPublisher(app.state.session_factory, dispatcher)
    assert await publisher.publish_once() is not None

    async with app.state.session_factory() as session:
        cancelled = await cancel_job(session, user, job.id)
        assert cancelled.state == JobState.CANCELLED

    from aetherflow.jobs.providers import create_default_provider_executor

    executor = create_default_provider_executor(app.state.settings)
    try:
        result = await Worker(
            app.state.session_factory,
            dispatcher,
            executor,
            worker_id="cancelled-schedule-worker",
        ).run_once()
    finally:
        await executor.close()

    assert result.status == WorkerResultStatus.INELIGIBLE
    async with app.state.session_factory() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None and stored.state == JobState.CANCELLED
        assert (
            await session.scalar(
                select(func.count())
                .select_from(JobEvent)
                .where(
                    JobEvent.job_id == job.id,
                    JobEvent.next_state == JobState.RUNNING,
                )
            )
            == 0
        )


@pytest.mark.asyncio
async def test_idempotency_conflict_includes_schedule_at(app) -> None:
    from aetherflow.api.errors import ApiError
    from aetherflow.auth.service import register_user

    first_at = datetime.now(UTC) + timedelta(hours=1)
    async with app.state.session_factory() as session:
        user = await register_user(
            session, "schedule-idem@example.com", "correct horse battery staple", None
        )
        await submit_job(
            session,
            user,
            JobCreateRequest(model="model", input={}, schedule_at=first_at),
            "schedule-idem-key",
        )
        with pytest.raises(ApiError) as exc_info:
            await submit_job(
                session,
                user,
                JobCreateRequest(
                    model="model",
                    input={},
                    schedule_at=first_at + timedelta(minutes=1),
                ),
                "schedule-idem-key",
            )
        assert exc_info.value.code == "IDEMPOTENCY_KEY_REUSED"
