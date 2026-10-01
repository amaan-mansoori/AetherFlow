"""Focused tests for the Phase 5 provider execution boundary."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select, update

from aetherflow.auth.service import register_user
from aetherflow.infrastructure.database.models import Job, JobAttempt, JobState
from aetherflow.jobs.dispatch import DispatchMessage, LocalDispatcher
from aetherflow.jobs.execution import (
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionOutcome,
    ExecutionRequest,
)
from aetherflow.jobs.providers import (
    MockProviderAdapter,
    ProviderExecutor,
    ProviderRegistry,
    create_default_provider_executor,
)
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.service import submit_job
from aetherflow.jobs.worker import Worker, WorkerResultStatus


async def create_provider_job(app, email: str, configuration: dict[str, object] | None = None):
    async with app.state.session_factory() as session:
        user = await register_user(session, email, "correct horse battery staple", None)
        job, _ = await submit_job(
            session,
            user,
            JobCreateRequest(
                model="mock-model",
                input={"prompt": "hello"},
                configuration=configuration or {},
            ),
            f"phase5-{email}",
        )
        return job


def message_for(job: Job) -> DispatchMessage:
    return DispatchMessage(job.id, job.version, datetime.now(UTC))


@pytest.mark.asyncio
async def test_mock_provider_normalizes_success() -> None:
    request = ExecutionRequest(
        UUID(int=1),
        "structured_inference",
        "mock-model",
        {"prompt": "hello"},
        {},
        5,
        {},
    )
    outcome = await MockProviderAdapter().execute(request)
    assert outcome.output == {"text": "hello"}
    assert outcome.provider == "mock"
    assert outcome.finish_reason == "stop"


@pytest.mark.asyncio
async def test_provider_registry_rejects_unsupported_provider_and_model() -> None:
    executor = ProviderExecutor(ProviderRegistry({"mock": MockProviderAdapter()}))
    request = ExecutionRequest(
        UUID(int=1),
        "structured_inference",
        "mock-model",
        {"prompt": "hello"},
        {"provider": "missing"},
        5,
        {},
    )
    with pytest.raises(ExecutionFailure) as missing:
        await executor.execute(request)
    assert missing.value.kind == ExecutionFailureKind.PERMANENT_PROVIDER


@pytest.mark.asyncio
async def test_provider_executor_rejects_malformed_normalized_output() -> None:
    class MalformedProvider:
        name = "malformed"

        def supports_model(self, model: str) -> bool:
            return True

        async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
            return ExecutionOutcome(output=None)  # type: ignore[arg-type]

    request = ExecutionRequest(
        UUID(int=1),
        "structured_inference",
        "model",
        {"prompt": "hello"},
        {"provider": "malformed"},
        5,
        {},
    )
    executor = ProviderExecutor(
        ProviderRegistry({"malformed": MalformedProvider()}),
    )
    with pytest.raises(ExecutionFailure) as failure:
        await executor.execute(request)
    assert failure.value.kind == ExecutionFailureKind.VALIDATION


@pytest.mark.asyncio
async def test_mock_provider_failure_categories_are_explicit() -> None:
    request = ExecutionRequest(
        UUID(int=1),
        "structured_inference",
        "mock-model",
        {"prompt": "hello"},
        {"mock_failure": "rate_limit"},
        5,
        {},
    )
    with pytest.raises(ExecutionFailure) as failure:
        await ProviderExecutor(ProviderRegistry({"mock": MockProviderAdapter()})).execute(request)
    assert failure.value.kind == ExecutionFailureKind.RATE_LIMIT
    assert failure.value.provider == "mock"


@pytest.mark.asyncio
async def test_provider_executor_worker_persists_normalized_provider(app) -> None:
    job = await create_provider_job(app, "phase5-success@example.com")
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    worker = Worker(
        app.state.session_factory,
        dispatcher,
        create_default_provider_executor(app.state.settings),
    )

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.SUCCEEDED
    async with app.state.session_factory() as session:
        attempt = await session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
        stored = await session.scalar(select(Job).where(Job.id == job.id))
        assert attempt is not None
        assert attempt.provider == "mock"
        assert stored is not None and stored.state == JobState.SUCCEEDED


@pytest.mark.asyncio
async def test_provider_failure_is_durable_and_acknowledged_after_decision(app) -> None:
    job = await create_provider_job(
        app,
        "phase5-rate-limit@example.com",
        {"mock_failure": "rate_limit"},
    )
    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    worker = Worker(
        app.state.session_factory,
        dispatcher,
        create_default_provider_executor(app.state.settings),
    )

    result = await worker.run_once()

    assert result.status == WorkerResultStatus.RETRY_SCHEDULED
    assert result.error_kind == ExecutionFailureKind.RATE_LIMIT
    async with app.state.session_factory() as session:
        attempt = await session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
        assert attempt is not None
        assert attempt.error_class == "RATE_LIMIT"
        assert attempt.provider == "mock"


@pytest.mark.asyncio
async def test_worker_timeout_is_durable(app) -> None:
    job = await create_provider_job(app, "phase5-timeout@example.com")
    async with app.state.session_factory() as session:
        await session.execute(update(Job).where(Job.id == job.id).values(timeout_seconds=0))
        await session.commit()

    class HangingExecutor:
        async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
            await asyncio.sleep(10)
            return ExecutionOutcome(output={"unreachable": True})

    dispatcher = LocalDispatcher()
    await dispatcher.dispatch(message_for(job))
    result = await Worker(app.state.session_factory, dispatcher, HangingExecutor()).run_once()

    assert result.status == WorkerResultStatus.RETRY_SCHEDULED
    assert result.error_kind == ExecutionFailureKind.TIMEOUT


def test_job_schema_rejects_provider_credentials() -> None:
    with pytest.raises(ValueError, match="provider credentials"):
        JobCreateRequest(
            model="mock-model",
            input={"prompt": "hello"},
            configuration={"api_key": "must-not-be-persisted"},
        )
