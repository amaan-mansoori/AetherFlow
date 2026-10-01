"""Focused tests for the Phase 4A execution and dispatch contracts."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select

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
    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        return ExecutionOutcome(output={"job_id": str(request.job_id), "ok": True})


@dataclass
class FailingExecutor:
    failure: ExecutionFailure

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        raise self.failure


class RaisingDispatcher:
    async def dispatch(self, message: DispatchMessage) -> None:
        raise DispatchFailure("dispatcher unavailable")

    async def receive(self) -> DispatchMessage:
        raise DispatchFailure("dispatcher unavailable")


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
        stored = await session.scalar(
            select(Job).options().where(Job.id == job.id)
        )
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
    await dispatcher.dispatch(
        DispatchMessage(job.id, job.version - 1, datetime.now(UTC))
    )
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
