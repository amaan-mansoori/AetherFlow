"""Deterministic Phase 6 execution retry and recovery tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from aetherflow.auth.service import register_user
from aetherflow.infrastructure.database.models import Job, JobAttempt, JobState, OutboxDispatch
from aetherflow.jobs.dispatch import DispatchMessage, LocalDispatcher
from aetherflow.jobs.execution import ExecutionFailure, ExecutionFailureKind, ExecutionOutcome
from aetherflow.jobs.outbox import OutboxPublisher
from aetherflow.jobs.retry import ExecutionRetryDecision, ExecutionRetryPolicy
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.service import cancel_job, submit_job
from aetherflow.jobs.worker import Worker, WorkerResultStatus


def test_execution_retry_policy_is_bounded_and_deterministic() -> None:
    policy = ExecutionRetryPolicy(
        max_attempts=3,
        initial_backoff_seconds=2,
        max_backoff_seconds=5,
        backoff_multiplier=3,
    )
    failure = ExecutionFailure(ExecutionFailureKind.TRANSIENT_PROVIDER, "temporary")

    assert policy.decision_for(failure, 1) == (
        ExecutionRetryDecision.RETRY,
        timedelta(seconds=2),
    )
    assert policy.decision_for(failure, 2) == (
        ExecutionRetryDecision.RETRY,
        timedelta(seconds=5),
    )
    assert policy.decision_for(failure, 3) == (ExecutionRetryDecision.TERMINAL, None)
    assert policy.decision_for(
        ExecutionFailure(ExecutionFailureKind.AUTHENTICATION, "invalid"), 1
    ) == (ExecutionRetryDecision.TERMINAL, None)


async def create_retry_job(app, email: str, retry_policy: dict[str, object] | None = None):
    async with app.state.session_factory() as session:
        user = await register_user(session, email, "correct horse battery staple", None)
        job, _ = await submit_job(
            session,
            user,
            JobCreateRequest(
                model="retry-model",
                input={"prompt": "retry"},
                retry_policy=retry_policy
                or {
                    "max_attempts": 2,
                    "initial_backoff_seconds": 10.0,
                    "max_backoff_seconds": 60.0,
                    "backoff_multiplier": 2.0,
                    "jitter": False,
                },
            ),
            f"phase6-{email}",
        )
        return job, user


def message_for(job: Job) -> DispatchMessage:
    return DispatchMessage(job.id, job.version, datetime.now(UTC))


class FailingOnceExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, request) -> ExecutionOutcome:
        self.calls += 1
        if self.calls == 1:
            raise ExecutionFailure(ExecutionFailureKind.TRANSIENT_PROVIDER, "temporary provider")
        return ExecutionOutcome(output={"ok": True}, provider="mock")


@pytest.mark.asyncio
async def test_retryable_failure_is_durable_and_reexecutes_as_second_attempt(app) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    job, _ = await create_retry_job(app, "phase6-retry@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    executor = FailingOnceExecutor()
    worker = Worker(app.state.session_factory, dispatcher, executor, now=lambda: now)

    first = await worker.run_once()

    assert first.status == WorkerResultStatus.RETRY_SCHEDULED
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        retry_intent = await session.scalar(
            select(OutboxDispatch).where(
                OutboxDispatch.job_id == job.id,
                OutboxDispatch.available_at.is_not(None),
            )
        )
        assert stored is not None and stored.state == JobState.RETRY_SCHEDULED
        assert retry_intent is not None
        assert retry_intent.job_version == stored.version
        assert retry_intent.available_at == (now + timedelta(seconds=10)).replace(tzinfo=None)
        attempts = list(
            (await session.scalars(select(JobAttempt).where(JobAttempt.job_id == job.id))).all()
        )
        assert len(attempts) == 1
        assert attempts[0].attempt_number == 1
        assert attempts[0].retry_decision == "RETRY"

    async with app.state.session_factory() as session:
        await session.execute(
            update(OutboxDispatch).where(OutboxDispatch.job_id == job.id).values(available_at=now)
        )
        await session.commit()
    publisher = OutboxPublisher(app.state.session_factory, dispatcher, now=lambda: now)
    assert await publisher.publish_once() is not None

    second = await worker.run_once()
    assert second.status == WorkerResultStatus.SUCCEEDED
    assert executor.calls == 2
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        attempts = list(
            (await session.scalars(select(JobAttempt).where(JobAttempt.job_id == job.id))).all()
        )
        assert stored is not None and stored.state == JobState.SUCCEEDED
        assert [attempt.attempt_number for attempt in attempts] == [1, 2]


@pytest.mark.asyncio
async def test_permanent_failure_exhaustion_is_terminal_without_retry_intent(app) -> None:
    job, _ = await create_retry_job(app, "phase6-permanent@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))

    class PermanentExecutor:
        async def execute(self, request) -> ExecutionOutcome:
            raise ExecutionFailure(ExecutionFailureKind.AUTHENTICATION, "bad configuration")

    result = await Worker(app.state.session_factory, dispatcher, PermanentExecutor()).run_once()

    assert result.status == WorkerResultStatus.FAILED
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        retry_intent = await session.scalar(
            select(OutboxDispatch).where(
                OutboxDispatch.job_id == job.id,
                OutboxDispatch.available_at.is_not(None),
            )
        )
        assert stored is not None and stored.state == JobState.FAILED
        assert retry_intent is None


@pytest.mark.asyncio
async def test_cancellation_wins_before_future_retry_dispatch(app) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    job, user = await create_retry_job(app, "phase6-cancel@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))

    class TransientExecutor:
        async def execute(self, request) -> ExecutionOutcome:
            raise ExecutionFailure(ExecutionFailureKind.TIMEOUT, "timeout")

    worker = Worker(app.state.session_factory, dispatcher, TransientExecutor(), now=lambda: now)
    assert (await worker.run_once()).status == WorkerResultStatus.RETRY_SCHEDULED

    async with app.state.session_factory() as session:
        await cancel_job(session, user, job.id)
    publisher = OutboxPublisher(
        app.state.session_factory,
        dispatcher,
        now=lambda: now + timedelta(seconds=30),
    )
    assert await publisher.publish_once() is not None
    assert (await worker.run_once()).status == WorkerResultStatus.CANCELLED

    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        assert stored is not None and stored.state == JobState.CANCELLED


@pytest.mark.asyncio
async def test_retry_budget_exhaustion_is_terminal_and_duplicate_delivery_is_ineligible(
    app,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    job, _ = await create_retry_job(app, "phase6-exhausted@example.com")

    class AlwaysTransientExecutor:
        async def execute(self, request) -> ExecutionOutcome:
            raise ExecutionFailure(ExecutionFailureKind.TRANSIENT_PROVIDER, "temporary")

    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    worker = Worker(
        app.state.session_factory,
        dispatcher,
        AlwaysTransientExecutor(),
        now=lambda: now,
    )
    assert (await worker.run_once()).status == WorkerResultStatus.RETRY_SCHEDULED

    async with app.state.session_factory() as session:
        await session.execute(
            update(OutboxDispatch)
            .where(
                OutboxDispatch.job_id == job.id,
                OutboxDispatch.available_at.is_not(None),
            )
            .values(available_at=now)
        )
        await session.commit()
    publisher = OutboxPublisher(app.state.session_factory, dispatcher, now=lambda: now)
    assert await publisher.publish_once() is not None
    retry_message = await dispatcher.receive()
    await dispatcher.dispatch(retry_message)
    assert (await worker.run_once()).status == WorkerResultStatus.FAILED

    await dispatcher.dispatch(retry_message)
    assert (await worker.run_once()).status == WorkerResultStatus.INELIGIBLE
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        attempts = list(
            (await session.scalars(select(JobAttempt).where(JobAttempt.job_id == job.id))).all()
        )
        assert stored is not None and stored.state == JobState.FAILED
        assert len(attempts) == 2
