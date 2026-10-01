"""Single-message worker orchestration with provider execution isolation."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from aetherflow.api.errors import ApiError
from aetherflow.infrastructure.database.models import Job, JobAttempt, JobState, utc_now
from aetherflow.jobs.dispatch import DispatchMessage, JobDispatcher
from aetherflow.jobs.execution import (
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionOutcome,
    ExecutionRequest,
    JobExecutor,
)
from aetherflow.jobs.service import (
    record_job_attempt,
    record_job_result,
    transition_job_state,
)
from aetherflow.jobs.state_machine import is_terminal_state


class WorkerResultStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INELIGIBLE = "INELIGIBLE"


@dataclass(frozen=True)
class WorkerResult:
    """Observable result of processing one dispatch message."""

    job_id: UUID
    status: WorkerResultStatus
    attempt_number: int | None = None
    error_kind: ExecutionFailureKind | None = None


class Worker:
    """Process one message while keeping execution outside DB transactions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dispatcher: JobDispatcher,
        executor: JobExecutor,
        worker_id: str = "local-worker",
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._executor = executor
        self._worker_id = worker_id

    async def run_once(self) -> WorkerResult:
        message = await self._dispatcher.receive()
        async with self._session_factory() as session:
            result = await self.process_message(session, message)
        await self._dispatcher.acknowledge(message)
        return result

    async def process_message(
        self, session: AsyncSession, message: DispatchMessage
    ) -> WorkerResult:
        job = await self._load_job(session, message.job_id)
        if job is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        if is_terminal_state(job.state):
            return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)

        if job.state == JobState.CANCEL_REQUESTED:
            await transition_job_state(
                session,
                job.id,
                JobState.CANCELLED,
                actor=self._worker_id,
                payload={"reason": "cancelled_before_execution"},
                expected_version=job.version,
            )
            return WorkerResult(message.job_id, WorkerResultStatus.CANCELLED)
        if job.state == JobState.RUNNING:
            if (
                job.execution_dispatch_version is not None
                and job.execution_dispatch_version != message.job_version
            ):
                return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)
            lease_until = job.execution_lease_until
            if lease_until is not None and lease_until.tzinfo is None:
                lease_until = lease_until.replace(tzinfo=UTC)
            if lease_until is None or lease_until <= datetime.now(UTC):
                return await self._recover_stale_execution(session, job)
            return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)
        if message.job_version != job.version:
            return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)

        if job.state == JobState.ACCEPTED:
            job = await transition_job_state(
                session,
                job.id,
                JobState.QUEUED,
                actor=self._worker_id,
                payload={"reason": "worker_accepted_dispatch"},
                expected_version=job.version,
            )
        if job.state == JobState.RETRY_SCHEDULED:
            job = await transition_job_state(
                session,
                job.id,
                JobState.QUEUED,
                actor=self._worker_id,
                payload={"reason": "retry_dispatch"},
                expected_version=job.version,
            )
        if job.state != JobState.QUEUED:
            return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)

        job = await transition_job_state(
            session,
            job.id,
            JobState.RUNNING,
            actor=self._worker_id,
            payload={"reason": "execution_started"},
            expected_version=job.version,
        )
        job.execution_owner = self._worker_id
        job.execution_dispatch_version = message.job_version
        job.execution_lease_until = utc_now() + timedelta(seconds=job.timeout_seconds + 30)
        attempt_number = len(job.attempts) + 1
        attempt = await record_job_attempt(
            session,
            job.id,
            attempt_number,
            "RUNNING",
            worker_id=self._worker_id,
            model=job.model,
        )
        request = ExecutionRequest(
            job_id=job.id,
            type=job.type,
            model=job.model,
            input=job.input,
            configuration=job.configuration,
            timeout_seconds=job.timeout_seconds,
            metadata=job.metadata_,
        )

        try:
            outcome = await asyncio.wait_for(
                self._executor.execute(request),
                timeout=request.timeout_seconds,
            )
        except TimeoutError:
            timeout_failure = ExecutionFailure(
                ExecutionFailureKind.TIMEOUT,
                "Execution exceeded the configured timeout.",
            )
            await self._finish_attempt(session, attempt.id, "FAILED", timeout_failure)
            await self._clear_execution_lease(session, job.id)
            await self._fail_job(session, job, timeout_failure)
            return WorkerResult(
                message.job_id,
                WorkerResultStatus.FAILED,
                attempt_number,
                timeout_failure.kind,
            )
        except ExecutionFailure as failure:
            await self._finish_attempt(session, attempt.id, "FAILED", failure)
            if failure.kind == ExecutionFailureKind.CANCELLATION:
                await self._clear_execution_lease(session, job.id)
                await self._cancel_after_execution_failure(session, job)
                return WorkerResult(
                    message.job_id,
                    WorkerResultStatus.CANCELLED,
                    attempt_number,
                    failure.kind,
                )
            await self._clear_execution_lease(session, job.id)
            await self._fail_job(session, job, failure)
            return WorkerResult(
                message.job_id,
                WorkerResultStatus.FAILED,
                attempt_number,
                failure.kind,
            )
        except Exception as exc:
            unexpected_failure = ExecutionFailure(ExecutionFailureKind.UNEXPECTED, str(exc))
            await self._finish_attempt(session, attempt.id, "FAILED", unexpected_failure)
            await self._clear_execution_lease(session, job.id)
            await self._fail_job(session, job, unexpected_failure)
            return WorkerResult(
                message.job_id,
                WorkerResultStatus.FAILED,
                attempt_number,
                unexpected_failure.kind,
            )

        await self._finish_attempt(session, attempt.id, "SUCCEEDED", None, outcome=outcome)
        await record_job_result(
            session,
            job.id,
            outcome.output,
            schema_version=outcome.schema_version,
            usage=outcome.usage,
        )
        await self._clear_execution_lease(session, job.id)
        current = await self._load_job(session, job.id)
        if current is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        await transition_job_state(
            session,
            job.id,
            JobState.SUCCEEDED,
            actor=self._worker_id,
            payload={"reason": "execution_succeeded"},
            expected_version=current.version,
        )
        return WorkerResult(message.job_id, WorkerResultStatus.SUCCEEDED, attempt_number)

    async def _recover_stale_execution(self, session: AsyncSession, job: Job) -> WorkerResult:
        target = JobState.SUCCEEDED if job.result is not None else JobState.FAILED
        job.execution_owner = None
        job.execution_dispatch_version = None
        job.execution_lease_until = None
        await transition_job_state(
            session,
            job.id,
            target,
            actor=self._worker_id,
            payload={
                "reason": "stale_execution_lease_recovered",
                "outcome": "result_present" if target == JobState.SUCCEEDED else "worker_crash",
            },
            expected_version=job.version,
        )
        return WorkerResult(
            job.id,
            WorkerResultStatus.SUCCEEDED
            if target == JobState.SUCCEEDED
            else WorkerResultStatus.FAILED,
        )

    async def _clear_execution_lease(self, session: AsyncSession, job_id: UUID) -> None:
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                execution_owner=None,
                execution_dispatch_version=None,
                execution_lease_until=None,
            )
        )

    async def _load_job(self, session: AsyncSession, job_id: UUID) -> Job | None:
        return await session.scalar(
            select(Job)
            .options(selectinload(Job.result), selectinload(Job.attempts))
            .where(Job.id == job_id)
        )

    async def _finish_attempt(
        self,
        session: AsyncSession,
        attempt_id: UUID,
        status: str,
        failure: ExecutionFailure | None,
        *,
        outcome: ExecutionOutcome | None = None,
    ) -> None:
        attempt = await session.get(JobAttempt, attempt_id)
        if attempt is None:
            raise ApiError("NOT_FOUND", "Job attempt not found.", 404)
        attempt.status = status
        attempt.completed_at = utc_now()
        if failure is not None:
            attempt.error_class = failure.kind.value
            attempt.error_message = failure.message[:4000]
            attempt.provider = failure.provider
        if outcome is not None:
            attempt.provider = outcome.provider
            attempt.usage = outcome.usage
        await session.commit()

    async def _fail_job(self, session: AsyncSession, job: Job, failure: ExecutionFailure) -> None:
        current = await self._load_job(session, job.id)
        if current is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        target = JobState.FAILED
        await transition_job_state(
            session,
            current.id,
            target,
            actor=self._worker_id,
            payload={"reason": "execution_failed", "failure_kind": failure.kind.value},
            expected_version=current.version,
        )

    async def _cancel_after_execution_failure(self, session: AsyncSession, job: Job) -> None:
        current = await self._load_job(session, job.id)
        if current is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        if current.state == JobState.RUNNING:
            current = await transition_job_state(
                session,
                current.id,
                JobState.CANCEL_REQUESTED,
                actor=self._worker_id,
                payload={"reason": "executor_cancellation"},
                expected_version=current.version,
            )
        if current.state == JobState.CANCEL_REQUESTED:
            await transition_job_state(
                session,
                current.id,
                JobState.CANCELLED,
                actor=self._worker_id,
                payload={"reason": "executor_cancellation_completed"},
                expected_version=current.version,
            )
