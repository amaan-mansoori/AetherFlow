"""Focused tests for the Phase 4A execution and dispatch contracts."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from aetherflow.infrastructure.database.models import Job, JobAttempt, JobState
from aetherflow.jobs.dispatch import DispatchFailure, DispatchMessage, LocalDispatcher
from aetherflow.jobs.execution import (
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionOutcome,
    ExecutionRequest,
)
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.service import cancel_job, submit_job
from aetherflow.jobs.worker import Worker, WorkerResultStatus


@dataclass
class SuccessfulExecutor:
    calls: int = 0

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        self.calls += 1
        return ExecutionOutcome(output={"job_id": str(request.job_id), "ok": True})


@dataclass
class FailingExecutor:
    failure: ExecutionFailure

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        raise self.failure


class RaisingDispatcher:
    acknowledgements: int = 0

    async def dispatch(self, message: DispatchMessage) -> None:
        raise DispatchFailure("dispatcher unavailable")

    async def receive(self) -> DispatchMessage:
        raise DispatchFailure("dispatcher unavailable")

    async def acknowledge(self, message: DispatchMessage) -> None:
        self.acknowledgements += 1

    async def close(self) -> None:
        return None


class TrackingDispatcher(LocalDispatcher):
    def __init__(self) -> None:
        super().__init__()
        self.acknowledgements = 0

    async def acknowledge(self, message: DispatchMessage) -> None:
        self.acknowledgements += 1


def message_for(job: Job) -> DispatchMessage:
    return DispatchMessage(
        job_id=job.id,
        job_version=job.version,
        enqueued_at=datetime.now(UTC),
    )


async def create_job(app, email: str) -> tuple[Job, object]:
    from aetherflow.auth.service import register_user

    async with app.state.session_factory() as session:
        user = await register_user(session, email, "correct horse battery staple", None)
        job, _ = await submit_job(
            session,
            user,
            JobCreateRequest(model="phase4a-test", input={"prompt": "test"}),
            f"phase4a-{email}",
        )
        return job, user


@pytest.mark.asyncio
async def test_local_dispatcher_round_trip() -> None:
    dispatcher = LocalDispatcher()
    message = DispatchMessage(UUID(int=1), 1, datetime.now(UTC))
    await dispatcher.dispatch(message)
    assert await dispatcher.receive() == message


@pytest.mark.asyncio
async def test_dispatcher_failure_is_explicit() -> None:
    dispatcher = RaisingDispatcher()
    message = DispatchMessage(UUID(int=1), 1, datetime.now(UTC))
    with pytest.raises(DispatchFailure, match="unavailable"):
        await dispatcher.dispatch(message)


@pytest.mark.asyncio
async def test_worker_success_records_attempt_result_and_transitions(app) -> None:
    job, _ = await create_job(app, "phase4a-success@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    worker = Worker(app.state.session_factory, dispatcher, SuccessfulExecutor())

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.SUCCEEDED
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).options().where(Job.id == job.id))
        assert stored is not None
        assert stored.state == JobState.SUCCEEDED
        attempt = await session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
        assert attempt is not None
        assert attempt.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_worker_execution_failure_records_failed_attempt_and_job(app) -> None:
    job, _ = await create_job(app, "phase4a-failure@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    worker = Worker(
        app.state.session_factory,
        dispatcher,
        FailingExecutor(ExecutionFailure(ExecutionFailureKind.EXECUTION, "provider failed")),
    )

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.FAILED
    assert result.error_kind == ExecutionFailureKind.EXECUTION
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        assert stored is not None
        assert stored.state == JobState.FAILED
        attempt = await session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
        assert attempt is not None
        assert attempt.status == "FAILED"
        assert attempt.error_class == "EXECUTION"


@pytest.mark.asyncio
async def test_worker_unexpected_exception_becomes_failed_execution(app) -> None:
    job, _ = await create_job(app, "phase4a-unexpected@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))

    class BrokenExecutor:
        async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
            raise RuntimeError("unexpected worker error")

    result = await Worker(app.state.session_factory, dispatcher, BrokenExecutor()).run_once()

    assert result.status == WorkerResultStatus.FAILED
    assert result.error_kind == ExecutionFailureKind.UNEXPECTED


@pytest.mark.asyncio
async def test_worker_exception_does_not_acknowledge_message(app) -> None:
    job, _ = await create_job(app, "phase4a-no-ack@example.com")
    dispatcher = TrackingDispatcher()
    await dispatcher.dispatch(message_for(job))

    class BrokenWorkerExecutor:
        async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
            raise KeyboardInterrupt

    worker = Worker(app.state.session_factory, dispatcher, BrokenWorkerExecutor())
    with pytest.raises(KeyboardInterrupt):
        await worker.run_once()

    assert dispatcher.acknowledgements == 0


@pytest.mark.asyncio
async def test_worker_cancels_job_before_execution_without_attempt(app) -> None:
    job, user = await create_job(app, "phase4a-cancel@example.com")
    async with app.state.session_factory() as session:
        await cancel_job(session, user, job.id)
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    worker = Worker(app.state.session_factory, dispatcher, SuccessfulExecutor())

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.CANCELLED
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        assert stored is not None
        assert stored.state == JobState.CANCELLED
        assert await session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id)) is None


@pytest.mark.asyncio
async def test_worker_rejects_stale_dispatch_version(app) -> None:
    job, _ = await create_job(app, "phase4a-stale@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(DispatchMessage(job.id, job.version - 1, datetime.now(UTC)))
    worker = Worker(app.state.session_factory, dispatcher, SuccessfulExecutor())

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.INELIGIBLE


@pytest.mark.asyncio
async def test_worker_rejects_terminal_job_as_ineligible(app) -> None:
    job, _ = await create_job(app, "phase4a-terminal@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    worker = Worker(app.state.session_factory, dispatcher, SuccessfulExecutor())
    assert (await worker.run_once()).status == WorkerResultStatus.SUCCEEDED

    await dispatcher.dispatch(message_for(job))
    result = await worker.run_once()

    assert result.status == WorkerResultStatus.INELIGIBLE


@pytest.mark.asyncio
async def test_worker_recovers_expired_execution_lease_after_restart(app) -> None:
    job, _ = await create_job(app, "phase4a-recovery@example.com")
    async with app.state.session_factory() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(
                state=JobState.RUNNING,
                version=2,
                execution_owner="crashed-worker",
                execution_lease_until=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        await session.commit()

    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(DispatchMessage(job.id, 2, datetime.now(UTC)))
    worker = Worker(app.state.session_factory, dispatcher, SuccessfulExecutor())
    result = await worker.run_once()

    assert result.status == WorkerResultStatus.FAILED
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        assert stored is not None
        assert stored.state == JobState.FAILED
        assert stored.execution_lease_until is None


@pytest.mark.asyncio
async def test_worker_recovers_original_dispatch_after_execution_crash(app) -> None:
    job, _ = await create_job(app, "phase4a-crash-redelivery@example.com")
    dispatcher = LocalDispatcher()
    message = message_for(job)
    await dispatcher.dispatch(message)
    worker = Worker(app.state.session_factory, dispatcher, SuccessfulExecutor())

    async with app.state.session_factory() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(
                state=JobState.RUNNING,
                version=3,
                execution_owner="crashed-worker",
                execution_dispatch_version=message.job_version,
                execution_lease_until=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        await session.commit()

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.FAILED
    assert worker._executor.calls == 0
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        assert stored is not None
        assert stored.state == JobState.FAILED


@pytest.mark.asyncio
async def test_worker_does_not_steal_active_execution_lease(app) -> None:
    job, _ = await create_job(app, "phase4a-active-lease@example.com")
    dispatcher = LocalDispatcher()
    message = message_for(job)
    await dispatcher.dispatch(message)
    executor = SuccessfulExecutor()
    worker = Worker(app.state.session_factory, dispatcher, executor, worker_id="worker-b")

    async with app.state.session_factory() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(
                state=JobState.RUNNING,
                version=3,
                execution_owner="worker-a",
                execution_dispatch_version=message.job_version,
                execution_lease_until=datetime.now(UTC) + timedelta(minutes=5),
            )
        )
        await session.commit()

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.INELIGIBLE
    assert executor.calls == 0


@pytest.mark.asyncio
async def test_worker_rejects_stale_message_for_running_execution(app) -> None:
    job, _ = await create_job(app, "phase4a-running-stale@example.com")
    dispatcher = LocalDispatcher()
    current_message = message_for(job)
    await dispatcher.dispatch(
        DispatchMessage(job.id, current_message.job_version - 1, current_message.enqueued_at)
    )
    executor = SuccessfulExecutor()
    worker = Worker(app.state.session_factory, dispatcher, executor, worker_id="worker-b")

    async with app.state.session_factory() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(
                state=JobState.RUNNING,
                version=3,
                execution_owner="worker-a",
                execution_dispatch_version=current_message.job_version,
                execution_lease_until=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
        await session.commit()

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.INELIGIBLE
    assert executor.calls == 0


@pytest.mark.asyncio
async def test_worker_recovers_expired_execution_with_durable_result(app) -> None:
    job, _ = await create_job(app, "phase4a-durable-result@example.com")
    dispatcher = LocalDispatcher()
    message = message_for(job)
    executor = SuccessfulExecutor()

    async with app.state.session_factory() as session:
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(
                state=JobState.RUNNING,
                version=3,
                execution_owner="crashed-worker",
                execution_dispatch_version=message.job_version,
                execution_lease_until=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        await session.commit()
        loaded = await session.scalar(
            select(Job).options(selectinload(Job.result)).where(Job.id == job.id)
        )
        assert loaded is not None
        from aetherflow.jobs.service import record_job_result

        await record_job_result(session, job.id, {"recovered": True})

    await dispatcher.dispatch(message)
    result = await Worker(
        app.state.session_factory, dispatcher, executor, worker_id="worker-b"
    ).run_once()

    assert result.status == WorkerResultStatus.SUCCEEDED
    assert executor.calls == 0
    async with app.state.session_factory() as session:
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        assert stored is not None
        assert stored.state == JobState.SUCCEEDED


@pytest.mark.asyncio
async def test_duplicate_dispatch_does_not_execute_terminal_job_again(app) -> None:
    job, _ = await create_job(app, "phase4a-duplicate@example.com")
    dispatcher = LocalDispatcher()
    executor = SuccessfulExecutor()
    message = message_for(job)
    await dispatcher.dispatch(message)
    worker = Worker(app.state.session_factory, dispatcher, executor)
    assert (await worker.run_once()).status == WorkerResultStatus.SUCCEEDED

    await dispatcher.dispatch(message)
    result = await worker.run_once()

    assert result.status == WorkerResultStatus.INELIGIBLE
    assert executor.calls == 1
